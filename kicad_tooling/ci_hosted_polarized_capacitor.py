"""Exact-version native fixture lane for polarized-capacitor orientation lint."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.component_polarized_capacitor_orientation import RULE_ID
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import KiCadErcReport, read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .validate import read_netlist

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

POLARIZED_CAPACITOR_FIXTURE_CASES = {
    "fault": "polarized-capacitor-native/fault.kicad_sch",
    "control": "polarized-capacitor-native/control.kicad_sch",
}


def _normalized_erc_digest(report: KiCadErcReport) -> str:
    violations: list[
        tuple[
            str,
            str,
            str | None,
            tuple[tuple[str | None, int | float | None, int | float | None], ...],
        ]
    ] = []
    for item in report.violations:
        details = tuple(
            sorted(
                ((detail.description, detail.x, detail.y) for detail in item.items),
                key=lambda detail: json.dumps(
                    detail,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ),
            )
        )
        violations.append((item.type, item.severity, item.description, details))
    violations.sort(
        key=lambda violation: json.dumps(
            violation,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )
    payload = json.dumps(
        {"kicad_version": report.kicad_version, "violations": violations},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def polarized_capacitor_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export, compare, and evaluate native polarized-capacitor fault/controls."""
    from .hwrepo.electrical import selected_config

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image or config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            "Polarized-capacitor fixtures require the pinned KiCad 10.0.0/10.0.5 images"
        )

    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    source_hashes = {
        case: digest(fixture_root / relative)
        for case, relative in POLARIZED_CAPACITOR_FIXTURE_CASES.items()
    }
    scratch = Path(tempfile.mkdtemp(prefix="polarized-capacitor-", dir=log.directory.resolve()))
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    source_lines = [
        'mkdir -p "$HOME"\n',
        'actual="$(kicad-cli version)"\n',
        'printf "kicad_version=%s\\n" "$actual"\n',
        f'test "$actual" = "{config.kicad_version}"\n',
    ]
    for case, relative in POLARIZED_CAPACITOR_FIXTURE_CASES.items():
        source_lines.append(f'printf "exporting_fixture=%s\\n" "{relative}"\n')
        for run in ("first", "repeat"):
            source_lines.extend(
                (
                    (
                        "kicad-cli sch export netlist --format kicadxml --output "
                        f'"/output/{case}.{run}.netlist.xml" "/fixtures/{relative}"\n'
                    ),
                    (
                        "kicad-cli sch erc --format json --severity-all --output "
                        f'"/output/{case}.{run}.erc.json" "/fixtures/{relative}"\n'
                    ),
                )
            )
    argv = (
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",
        *user,
        "-e",
        "HOME=/tmp/kicad-polarized-capacitor-fixtures",
        "-v",
        f"{fixture_root.resolve()}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned_image(config.image),
        "-ec",
        "".join(source_lines),
    )
    log.event(
        "polarized-capacitor-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=config.image,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(
            f"Native polarized-capacitor export failed: {command.stderr or command.error}"
        )

    log.event(
        "polarized-capacitor-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=config.image,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in source_hashes),
        command_receipt=receipt.relative_to(root).as_posix(),
    )

    netlist_hashes: dict[tuple[str, str], str] = {}
    erc_hashes: dict[tuple[str, str], str] = {}
    reports_by_case: dict[str, dict[str, DesignLintReport]] = {}
    erc_error_types: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in POLARIZED_CAPACITOR_FIXTURE_CASES:
        reports_by_case[case] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            observed = read_netlist(netlist_path)
            normalized_netlist = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            netlist_hashes[(case, run)] = hashlib.sha256(normalized_netlist).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != config.kicad_version:
                raise ValueError(
                    "Polarized-capacitor ERC report differs from selected KiCad version"
                )
            erc_hashes[(case, run)] = _normalized_erc_digest(erc)
            erc_error_types[(case, run)] = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            if erc_error_types[(case, run)]:
                raise ValueError(
                    f"Native polarized-capacitor fixture has ERC errors: "
                    f"{erc_error_types[(case, run)]}"
                )
            reports_by_case[case][run] = evaluate(
                f"synthetic-polarized-capacitor-{case}",
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=f"synthetic-polarized-capacitor-{case}",
                    observed=observed,
                    netlist_sha256=digest(netlist_path),
                ),
                DesignLintPolicy(),
            )

    for case, runs in reports_by_case.items():
        if netlist_hashes[(case, "first")] != netlist_hashes[(case, "repeat")]:
            raise ValueError(
                f"Native polarized-capacitor {case} netlist differs after normalization"
            )
        if erc_hashes[(case, "first")] != erc_hashes[(case, "repeat")]:
            raise ValueError(f"Native polarized-capacitor {case} ERC differs after normalization")
        if runs["first"].model_dump(mode="json") != runs["repeat"].model_dump(mode="json"):
            raise ValueError(f"Native polarized-capacitor {case} finding differs between repeats")
        findings = tuple(item for item in runs["first"].findings if item.rule_id == RULE_ID)
        expected_count = 1 if case == "fault" else 0
        if len(findings) != expected_count:
            raise ValueError(
                f"Native polarized-capacitor {case} expected {expected_count} finding(s), "
                f"observed {len(findings)}"
            )
        log.event(
            f"polarized-capacitor-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=config.image,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=netlist_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=netlist_hashes[(case, "repeat")],
            normalized_erc_sha256=erc_hashes[(case, "first")],
            repeat_normalized_erc_sha256=erc_hashes[(case, "repeat")],
            rule_findings="; ".join(item.subject for item in findings) if findings else "none",
            erc_errors="none",
            repeatable="true",
        )
