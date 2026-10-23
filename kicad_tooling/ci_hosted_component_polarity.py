"""Shared exact-version native acceptance for component polarity lint fixtures."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import KiCadErcReport, read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .validate import read_netlist

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


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


def component_polarity_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
    fixture_prefix: str,
    project_id_prefix: str,
    rule_id: str,
    fixtures: dict[str, str],
    expected_subjects: dict[str, str | None],
) -> None:
    """Export and compare source-hashed polarity fault/control fixtures twice."""
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image or config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError("Component polarity fixtures require pinned KiCad 10.0.0/10.0.5 images")
    if not fixtures or set(fixtures) != set(expected_subjects):
        raise ValueError("Every component-polarity fixture requires one expected target finding")

    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    source_hashes = {case: digest(fixture_root / path) for case, path in fixtures.items()}
    scratch = Path(tempfile.mkdtemp(prefix=f"{fixture_prefix}-", dir=log.directory.resolve()))
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
    for case, relative in fixtures.items():
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
        f"HOME=/tmp/kicad-{fixture_prefix}",
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
        f"{fixture_prefix}/native-export",
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
            f"Native component polarity export failed: {command.stderr or command.error}"
        )
    log.event(
        f"{fixture_prefix}/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=config.image,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in fixtures),
        command_receipt=receipt.relative_to(root).as_posix(),
    )

    hashes: dict[tuple[str, str, str], str] = {}
    erc_errors: dict[tuple[str, str], tuple[str, ...]] = {}
    reports: dict[str, dict[str, DesignLintReport]] = {}
    for case in fixtures:
        reports[case] = {}
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
            hashes[(case, run, "netlist")] = hashlib.sha256(normalized_netlist).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != config.kicad_version:
                raise ValueError(
                    "Component polarity ERC report differs from selected KiCad version"
                )
            hashes[(case, run, "erc")] = _normalized_erc_digest(erc)
            erc_errors[(case, run)] = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            if erc_errors[(case, run)]:
                raise ValueError(
                    f"Native component polarity fixture has ERC errors: {erc_errors[(case, run)]}"
                )
            project_id = f"{project_id_prefix}-{case}"
            reports[case][run] = evaluate(
                project_id,
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=project_id,
                    observed=observed,
                    netlist_sha256=digest(netlist_path),
                ),
                DesignLintPolicy(),
            )

    for case, runs in reports.items():
        if hashes[(case, "first", "netlist")] != hashes[(case, "repeat", "netlist")]:
            raise ValueError(
                f"Native component polarity {case} netlist differs after normalization"
            )
        if hashes[(case, "first", "erc")] != hashes[(case, "repeat", "erc")]:
            raise ValueError(f"Native component polarity {case} ERC differs after normalization")
        if (
            runs["first"].status != runs["repeat"].status
            or runs["first"].findings != runs["repeat"].findings
        ):
            raise ValueError(f"Native component polarity {case} finding differs between repeats")
        findings = tuple(item for item in runs["first"].findings if item.rule_id == rule_id)
        expected = expected_subjects[case]
        if tuple(item.subject for item in findings) != (() if expected is None else (expected,)):
            raise ValueError(
                f"Native component polarity {case} target findings differ from expectation"
            )
        log.event(
            f"{fixture_prefix}/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=config.image,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=hashes[(case, "first", "netlist")],
            repeat_normalized_netlist_sha256=hashes[(case, "repeat", "netlist")],
            normalized_erc_sha256=hashes[(case, "first", "erc")],
            repeat_normalized_erc_sha256=hashes[(case, "repeat", "erc")],
            rule_findings="; ".join(item.subject for item in findings) if findings else "none",
            erc_errors="none",
            repeatable="true",
        )
