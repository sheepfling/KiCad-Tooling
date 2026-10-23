"""Exact-version native fixtures for the MOSFET gate peer heuristic."""

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
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .hwrepo.mosfet_gate_connectivity import RULE_ID
from .validate import read_netlist

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

MOSFET_GATE_FIXTURE_CASES = {
    "fault": "mosfet-gate-native/fault.kicad_sch",
    "control": "mosfet-gate-native/control.kicad_sch",
}
ErcDetailRow = tuple[str | None, int | float | None, int | float | None]
ErcViolationRow = tuple[str, str, str | None, tuple[ErcDetailRow, ...]]


def _normalized_erc_report(report: KiCadErcReport) -> bytes:
    """Serialize every typed ERC detail in stable order, excluding raw JSON ordering."""
    violations: list[ErcViolationRow] = []
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
    return json.dumps(
        {"kicad_version": report.kicad_version, "violations": violations},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def mosfet_gate_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export and evaluate the isolated native gate fault/control pair twice."""
    from .hwrepo.electrical import selected_config

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image or config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError("MOSFET gate fixtures require the selected exact KiCad 10.0 image")
    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    source_hashes = {
        case: digest(fixture_root / relative)
        for case, relative in MOSFET_GATE_FIXTURE_CASES.items()
    }
    scratch = Path(tempfile.mkdtemp(prefix="mosfet-gate-", dir=log.directory.resolve()))
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
    for case, relative in MOSFET_GATE_FIXTURE_CASES.items():
        source_lines.append(f'printf "exporting_fixture=%s\\n" "{relative}"\n')
        for run in ("first", "repeat"):
            source_lines.append(
                f"kicad-cli sch export netlist --format kicadxml --output "
                f'"/output/{case}.{run}.netlist.xml" "/fixtures/{relative}"\n'
            )
            source_lines.append(
                f"kicad-cli sch erc --format json --severity-all --output "
                f'"/output/{case}.{run}.erc.json" "/fixtures/{relative}"\n'
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
        "HOME=/tmp/kicad-mosfet-gate-fixtures",
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
        "mosfet-gate-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=config.image,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(f"Native MOSFET gate export failed: {command.stderr or command.error}")

    log.event(
        "mosfet-gate-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=config.image,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in source_hashes),
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    normalized_hashes: dict[tuple[str, str], str] = {}
    erc_hashes: dict[tuple[str, str], str] = {}
    erc_warning_counts: dict[tuple[str, str], int] = {}
    for case in MOSFET_GATE_FIXTURE_CASES:
        reports: dict[str, DesignLintReport] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != config.kicad_version:
                raise ValueError("MOSFET gate ERC report differs from selected KiCad version")
            erc_hashes[(case, run)] = hashlib.sha256(_normalized_erc_report(erc)).hexdigest()
            erc_errors = tuple(item.type for item in erc.violations if item.severity == "error")
            erc_warning_counts[(case, run)] = sum(
                item.severity == "warning" for item in erc.violations
            )
            if erc_errors:
                raise ValueError(f"Native MOSFET gate fixture has ERC errors: {erc_errors}")
            report = evaluate(
                f"synthetic-mosfet-gate-{case}",
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=f"synthetic-mosfet-gate-{case}",
                    observed=observed,
                    netlist_sha256=digest(netlist_path),
                ),
                DesignLintPolicy(),
            )
            reports[run] = report
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native MOSFET gate {case} netlist differs after normalization")
        if erc_hashes[(case, "first")] != erc_hashes[(case, "repeat")]:
            raise ValueError(f"Native MOSFET gate {case} ERC differs after normalization")
        findings_by_run = {
            run: tuple(
                item.model_dump(mode="json") for item in report.findings if item.rule_id == RULE_ID
            )
            for run, report in reports.items()
        }
        if findings_by_run["first"] != findings_by_run["repeat"]:
            raise ValueError(f"Native MOSFET gate {case} candidates differ between repeats")
        findings = tuple(item for item in reports["first"].findings if item.rule_id == RULE_ID)
        expected_count = 1 if case == "fault" else 0
        if len(findings) != expected_count:
            raise ValueError(
                f"Native MOSFET gate {case} expected {expected_count} finding(s), "
                f"observed {len(findings)}"
            )
        log.event(
            f"mosfet-gate-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=config.image,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            normalized_erc_sha256=erc_hashes[(case, "first")],
            repeat_normalized_erc_sha256=erc_hashes[(case, "repeat")],
            lint_status=reports["first"].status,
            rule_findings=";".join(item.subject for item in findings) or "none",
            erc_warning_count=erc_warning_counts[(case, "first")],
            erc_errors="none",
            repeatable="true",
        )
    if any(
        digest(fixture_root / relative) != source_hashes[case]
        for case, relative in MOSFET_GATE_FIXTURE_CASES.items()
    ):
        raise ValueError("MOSFET gate fixture sources changed during native export")
