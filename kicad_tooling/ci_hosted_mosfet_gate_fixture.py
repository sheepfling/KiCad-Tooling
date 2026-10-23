"""Exact-version native fixtures for focused MOSFET schematic heuristics."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_support import normalized_erc_report_bytes
from .hwrepo.component_mosfet_gate_drive import RULE_ID as DIRECT_DRIVE_RULE_ID
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_component_mosfet_terminals import (
    GATE_DRAIN_RULE_ID as GATE_DRAIN_SAME_NET_RULE_ID,
)
from .hwrepo.design_lint_component_mosfet_terminals import (
    GATE_SOURCE_RULE_ID as GATE_SOURCE_SAME_NET_RULE_ID,
)
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy, DesignLintRuleOverride
from .hwrepo.mosfet_gate_connectivity import RULE_ID, SOURCE_BIAS_RULE_ID
from .validate import read_netlist

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

MOSFET_GATE_FIXTURE_CASES = {
    "fault": "mosfet-gate-native/fault.kicad_sch",
    "control": "mosfet-gate-native/control.kicad_sch",
    "source-bias-control": "mosfet-gate-native/source-bias-control.kicad_sch",
    "series-gate-control": "mosfet-gate-native/series-gate-control.kicad_sch",
    "gate-source-fault": "mosfet-gate-native/gate-source-tie.kicad_sch",
    "gate-source-control": "mosfet-gate-native/source-bias-control.kicad_sch",
    "gate-drain-fault": "mosfet-gate-native/gate-drain-tie.kicad_sch",
    "gate-drain-control": "mosfet-gate-native/source-bias-control.kicad_sch",
}


def mosfet_gate_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export and evaluate native MOSFET gate connectivity heuristics twice."""
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
            erc_hashes[(case, run)] = hashlib.sha256(normalized_erc_report_bytes(erc)).hexdigest()
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
                DesignLintPolicy(
                    rules=(
                        DesignLintRuleOverride(
                            rule_id=SOURCE_BIAS_RULE_ID,
                            mode="review",
                            reason="Native synthetic source-bias fixture",
                        ),
                        DesignLintRuleOverride(
                            rule_id=DIRECT_DRIVE_RULE_ID,
                            mode="review",
                            reason="Native synthetic series-gate fixture",
                        ),
                        DesignLintRuleOverride(
                            rule_id=GATE_SOURCE_SAME_NET_RULE_ID,
                            mode="review",
                            reason="Native synthetic MOSFET gate/source tie fixture",
                        ),
                        DesignLintRuleOverride(
                            rule_id=GATE_DRAIN_SAME_NET_RULE_ID,
                            mode="review",
                            reason="Native synthetic MOSFET gate/drain tie fixture",
                        ),
                    )
                ),
            )
            reports[run] = report
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native MOSFET gate {case} netlist differs after normalization")
        if erc_hashes[(case, "first")] != erc_hashes[(case, "repeat")]:
            raise ValueError(f"Native MOSFET gate {case} ERC differs after normalization")
        findings_by_rule_and_run = {
            rule_id: {
                run: tuple(
                    item.model_dump(mode="json")
                    for item in report.findings
                    if item.rule_id == rule_id
                )
                for run, report in reports.items()
            }
            for rule_id in (
                RULE_ID,
                SOURCE_BIAS_RULE_ID,
                DIRECT_DRIVE_RULE_ID,
                GATE_SOURCE_SAME_NET_RULE_ID,
                GATE_DRAIN_SAME_NET_RULE_ID,
            )
        }
        if any(by_run["first"] != by_run["repeat"] for by_run in findings_by_rule_and_run.values()):
            raise ValueError(f"Native MOSFET gate {case} candidates differ between repeats")
        gate_findings = tuple(item for item in reports["first"].findings if item.rule_id == RULE_ID)
        bias_findings = tuple(
            item for item in reports["first"].findings if item.rule_id == SOURCE_BIAS_RULE_ID
        )
        direct_drive_findings = tuple(
            item for item in reports["first"].findings if item.rule_id == DIRECT_DRIVE_RULE_ID
        )
        gate_source_findings = tuple(
            item
            for item in reports["first"].findings
            if item.rule_id == GATE_SOURCE_SAME_NET_RULE_ID
        )
        gate_drain_findings = tuple(
            item
            for item in reports["first"].findings
            if item.rule_id == GATE_DRAIN_SAME_NET_RULE_ID
        )
        expected_gate_count = 1 if case == "fault" else 0
        expected_bias_count = 1 if case == "control" else 0
        expected_direct_drive_count = (
            1
            if case
            in {
                "control",
                "source-bias-control",
                "gate-source-fault",
                "gate-source-control",
                "gate-drain-fault",
                "gate-drain-control",
            }
            else 0
        )
        expected_gate_source_count = 1 if case == "gate-source-fault" else 0
        expected_gate_drain_count = 1 if case == "gate-drain-fault" else 0
        if len(gate_findings) != expected_gate_count:
            raise ValueError(
                f"Native MOSFET gate {case} expected {expected_gate_count} finding(s), "
                f"observed {len(gate_findings)}"
            )
        if len(bias_findings) != expected_bias_count:
            raise ValueError(
                f"Native MOSFET source-bias {case} expected {expected_bias_count} finding(s), "
                f"observed {len(bias_findings)}"
            )
        if len(direct_drive_findings) != expected_direct_drive_count:
            raise ValueError(
                f"Native MOSFET direct-drive {case} expected {expected_direct_drive_count} finding(s), "
                f"observed {len(direct_drive_findings)}"
            )
        if len(gate_source_findings) != expected_gate_source_count:
            raise ValueError(
                f"Native MOSFET gate/source {case} expected {expected_gate_source_count} "
                f"finding(s), observed {len(gate_source_findings)}"
            )
        if len(gate_drain_findings) != expected_gate_drain_count:
            raise ValueError(
                f"Native MOSFET gate/drain {case} expected {expected_gate_drain_count} "
                f"finding(s), observed {len(gate_drain_findings)}"
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
            rule_findings=";".join(item.subject for item in gate_findings) or "none",
            source_bias_rule_findings=";".join(item.subject for item in bias_findings) or "none",
            direct_drive_rule_findings=";".join(item.subject for item in direct_drive_findings)
            or "none",
            gate_source_rule_findings=";".join(item.subject for item in gate_source_findings)
            or "none",
            gate_drain_rule_findings=";".join(item.subject for item in gate_drain_findings)
            or "none",
            erc_warning_count=erc_warning_counts[(case, "first")],
            erc_errors="none",
            repeatable="true",
        )
    if any(
        digest(fixture_root / relative) != source_hashes[case]
        for case, relative in MOSFET_GATE_FIXTURE_CASES.items()
    ):
        raise ValueError("MOSFET gate fixture sources changed during native export")
