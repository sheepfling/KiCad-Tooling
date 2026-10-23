"""Exact-version native fixture lane for MOSFET drain/source same-net lint."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_support import normalized_erc_report_bytes
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_finding_models import DesignLintFinding, DesignLintRuleOverride
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .validate import read_netlist

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

RULE_ID = "component.mosfet_drain_source_same_net"
FIXTURE_CASES = {
    "fault": "mosfet-drain-source-native/fault.kicad_sch",
    "control": "mosfet-gate-native/control.kicad_sch",
}


def mosfet_drain_source_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export exact-version fault/control schematics and compare native evidence."""
    from .hwrepo.electrical import selected_config

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image or config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError("MOSFET same-net fixtures require the exact selected KiCad 10.0 image")
    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    source_hashes = {
        case: digest(fixture_root / relative) for case, relative in FIXTURE_CASES.items()
    }
    scratch = Path(tempfile.mkdtemp(prefix="mosfet-same-net-", dir=log.directory.resolve()))
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
    for case, relative in FIXTURE_CASES.items():
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
        "HOME=/tmp/kicad-mosfet-same-net-fixtures",
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
        "mosfet-drain-source-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=config.image,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(f"Native MOSFET same-net export failed: {command.stderr or command.error}")
    log.event(
        "mosfet-drain-source-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=config.image,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in FIXTURE_CASES),
        command_receipt=receipt.relative_to(root).as_posix(),
    )

    for case in FIXTURE_CASES:
        netlist_hashes: list[str] = []
        erc_hashes: list[str] = []
        findings_by_run: list[tuple[DesignLintFinding, ...]] = []
        report_statuses: list[str] = []
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
            netlist_hashes.append(hashlib.sha256(normalized_netlist).hexdigest())
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != config.kicad_version:
                raise ValueError("MOSFET same-net ERC version differs from project pin")
            if any(item.severity == "error" for item in erc.violations):
                raise ValueError(f"Native MOSFET same-net {case} fixture has ERC errors")
            erc_hashes.append(hashlib.sha256(normalized_erc_report_bytes(erc)).hexdigest())
            report = evaluate(
                f"synthetic-mosfet-same-net-{case}",
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=f"synthetic-mosfet-same-net-{case}",
                    observed=observed,
                    netlist_sha256=digest(netlist_path),
                ),
                DesignLintPolicy(
                    rules=(
                        DesignLintRuleOverride(
                            rule_id=RULE_ID,
                            mode="review",
                            reason="Native synthetic MOSFET same-net fixture",
                        ),
                    )
                ),
            )
            selected = tuple(item for item in report.findings if item.rule_id == RULE_ID)
            findings_by_run.append(selected)
            report_statuses.append(report.status)

        expected = 1 if case == "fault" else 0
        if netlist_hashes[0] != netlist_hashes[1] or erc_hashes[0] != erc_hashes[1]:
            raise ValueError(f"Native MOSFET same-net {case} evidence is not repeatable")
        if findings_by_run[0] != findings_by_run[1] or len(findings_by_run[0]) != expected:
            raise ValueError(f"Native MOSFET same-net {case} expected {expected} stable finding(s)")
        expected_status = "REVIEW" if expected else "PASS"
        if report_statuses != [expected_status, expected_status]:
            raise ValueError(f"Native MOSFET same-net {case} has unexpected lint status")
        log.event(
            f"mosfet-drain-source-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=config.image,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=netlist_hashes[0],
            repeat_normalized_netlist_sha256=netlist_hashes[1],
            normalized_erc_sha256=erc_hashes[0],
            repeat_normalized_erc_sha256=erc_hashes[1],
            lint_status=report_statuses[0],
            rule_findings=";".join(item.subject for item in findings_by_run[0]) or "none",
            erc_errors="none",
            repeatable="true",
        )

    if any(
        digest(fixture_root / relative) != source_hashes[case]
        for case, relative in FIXTURE_CASES.items()
    ):
        raise ValueError("MOSFET same-net fixture sources changed during native export")
