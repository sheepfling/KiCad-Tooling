"""Exact-version native fixture lane for transformer winding same-net lint."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from .ci_hosted_support import HostedLog, normalized_erc_report_bytes, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .validate import read_netlist

RULE_ID = "component.transformer_winding_same_net"
GROUP_BRIDGE_RULE_ID = "component.transformer_winding_groups_share_net"
FIXTURE_CASES: Mapping[str, str] = MappingProxyType(
    {
        "fault": "transformer-windings/same-net-winding-1.kicad_sch",
        "cross_winding_fault": "transformer-windings/shared-winding-groups-net.kicad_sch",
        "control": "transformer-windings/distinct-winding-terminal-nets.kicad_sch",
    }
)
EXPECTED_FINDINGS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "fault": ("T1: winding 1 pins 1/2 share WINDING_1_TIED",),
        "cross_winding_fault": (),
        "control": (),
    }
)
EXPECTED_GROUP_BRIDGE_FINDINGS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "fault": (),
        "cross_winding_fault": ("T1: winding groups share WINDING_GROUPS_SHARED",),
        "control": (),
    }
)


def transformer_winding_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export exact-version fault/control schematics and compare native evidence."""
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image or config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError("Transformer winding fixtures require a pinned KiCad 10.0 image")
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint"
    source_hashes = {
        case: digest(fixture_root / relative) for case, relative in FIXTURE_CASES.items()
    }
    scratch = Path(tempfile.mkdtemp(prefix="transformer-winding-", dir=log.directory.resolve()))
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
        "HOME=/tmp/kicad-transformer-winding-fixtures",
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
        "transformer-winding-fixture/native-export",
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
            f"Native transformer winding export failed: {command.stderr or command.error}"
        )
    log.event(
        "transformer-winding-fixture/native-export",
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
        finding_subjects: list[tuple[str, ...]] = []
        group_bridge_subjects: list[tuple[str, ...]] = []
        lint_statuses: list[str] = []
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            observed = read_netlist(netlist_path)
            if observed.component_symbols.get("T1") != "Transformer:TRANSF1":
                raise ValueError("Native transformer fixture lost the exact TRANSF1 identity")
            if set(observed.component_pin_numbers.get("T1", ())) != {"1", "2", "3", "4"}:
                raise ValueError("Native transformer fixture has an unexpected pin inventory")
            normalized_netlist = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            netlist_hashes.append(hashlib.sha256(normalized_netlist).hexdigest())
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != config.kicad_version:
                raise ValueError("Transformer winding ERC version differs from project pin")
            if any(item.severity == "error" for item in erc.violations):
                raise ValueError(f"Native transformer winding {case} fixture has ERC errors")
            erc_hashes.append(hashlib.sha256(normalized_erc_report_bytes(erc)).hexdigest())
            report = evaluate(
                f"synthetic-transformer-winding-{case}",
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=f"synthetic-transformer-winding-{case}",
                    observed=observed,
                    netlist_sha256=digest(netlist_path),
                ),
                DesignLintPolicy(),
            )
            finding_subjects.append(
                tuple(item.subject for item in report.findings if item.rule_id == RULE_ID)
            )
            group_bridge_subjects.append(
                tuple(
                    item.subject for item in report.findings if item.rule_id == GROUP_BRIDGE_RULE_ID
                )
            )
            lint_statuses.append(report.status)

        expected = EXPECTED_FINDINGS[case]
        expected_group_bridge = EXPECTED_GROUP_BRIDGE_FINDINGS[case]
        if netlist_hashes[0] != netlist_hashes[1] or erc_hashes[0] != erc_hashes[1]:
            raise ValueError(f"Native transformer winding {case} evidence is not repeatable")
        if finding_subjects != [expected, expected] or group_bridge_subjects != [
            expected_group_bridge,
            expected_group_bridge,
        ]:
            raise ValueError(f"Native transformer winding {case} findings differ from expectation")
        expected_status = "REVIEW" if expected or expected_group_bridge else "PASS"
        if lint_statuses != [expected_status, expected_status]:
            raise ValueError(f"Native transformer winding {case} has unexpected lint status")
        log.event(
            f"transformer-winding-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=config.image,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=netlist_hashes[0],
            repeat_normalized_netlist_sha256=netlist_hashes[1],
            normalized_erc_sha256=erc_hashes[0],
            repeat_normalized_erc_sha256=erc_hashes[1],
            lint_status=lint_statuses[0],
            rule_findings=";".join(finding_subjects[0]) or "none",
            group_bridge_rule_findings=";".join(group_bridge_subjects[0]) or "none",
            erc_errors="none",
            repeatable="true",
        )

    if any(
        digest(fixture_root / relative) != source_hashes[case]
        for case, relative in FIXTURE_CASES.items()
    ):
        raise ValueError("Transformer winding fixture sources changed during native export")
