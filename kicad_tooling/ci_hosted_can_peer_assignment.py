"""Hosted native CAN peer assignment fixture lane."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import read_kicad_erc_report, write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def can_peer_assignment_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify cross-peer CAN pair review from repeated pinned native exports."""
    import hashlib

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintFinding,
        DesignLintPolicy,
        DesignLintReport,
        NetlistContract,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"CAN peer fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/can-peer-native"
    )
    cases = ("peer-control", "peer-fault")
    source_hashes = {case: digest(fixture_root / f"{case}.kicad_sch") for case in cases}
    scratch = Path(tempfile.mkdtemp(prefix=f"can-peer-{project}-", dir=log.directory.resolve()))
    inputs = scratch / "input"
    inputs.mkdir()
    for case in cases:
        fixture = fixture_root / f"{case}.kicad_sch"
        copied = inputs / fixture.name
        shutil.copyfile(fixture, copied)
        if digest(copied) != source_hashes[case]:
            raise ValueError(f"Synthetic CAN {case} fixture changed while preparing native input")
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{config.kicad_version}"\n'
        "for case in peer-control peer-fault; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${case}.${run}.netlist.xml" '
        '      "/fixtures/${case}.kicad_sch"\n'
        "    kicad-cli sch erc --format json --severity-all "
        '      --output "/output/${case}.${run}.erc.json" '
        '      "/fixtures/${case}.kicad_sch"\n'
        "  done\n"
        "done\n"
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
        "HOME=/tmp/kicad-can-peer-fixtures",
        "-v",
        f"{inputs}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        script,
    )
    log.event(
        "can-peer-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{source_hashes[case]}" for case in cases),
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "can-peer-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native CAN peer fixture command failed: {command.stderr or command.error}"
        )

    logs: dict[
        str,
        tuple[DesignLintReport, tuple[DesignLintFinding, ...], str, tuple[str, ...]],
    ] = {}
    for case in cases:
        observed_by_run: dict[str, NetlistContract] = {}
        normalized_hashes: dict[str, str] = {}
        normalized_erc_hashes: dict[str, str] = {}
        erc_warning_types: dict[str, tuple[str, ...]] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native CAN peer {case} export omitted an expected report")
            observed = read_netlist(netlist_path)
            observed_by_run[run] = observed
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[run] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != config.kicad_version:
                raise ValueError(
                    f"Native CAN peer {case} ERC report version differs from KiCad "
                    f"{config.kicad_version}"
                )
            erc_rows = [
                (
                    item.type,
                    item.severity,
                    item.description,
                    tuple(
                        sorted(
                            [(detail.description, detail.x, detail.y) for detail in item.items],
                            key=lambda detail: json.dumps(
                                detail,
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False,
                            ),
                        )
                    ),
                )
                for item in erc.violations
            ]
            erc_rows.sort(
                key=lambda item: json.dumps(
                    item,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
            normalized_erc = json.dumps(
                {"kicad_version": erc.kicad_version, "violations": erc_rows},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_erc_hashes[run] = hashlib.sha256(normalized_erc).hexdigest()
            erc_errors = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            if erc_errors:
                raise ValueError(f"Native CAN peer {case} has unexpected ERC errors: {erc_errors}")
            erc_warning_types[run] = tuple(
                sorted({item.type for item in erc.violations if item.severity == "warning"})
            )
        if normalized_hashes["first"] != normalized_hashes["repeat"]:
            raise ValueError(f"Native CAN peer {case} exports are not repeatable")
        if normalized_erc_hashes["first"] != normalized_erc_hashes["repeat"]:
            raise ValueError(f"Native CAN peer {case} ERC reports are not repeatable")
        observed = observed_by_run["first"]
        expected_functions: dict[str, str] = {
            "U1.1": "CANH",
            "U1.2": "CAN_L",
            "U2.1": "CANH",
            "U2.2": "CAN_L",
            "U3.1": "CANH",
            "U3.2": "CAN_L",
        }
        if observed.pin_functions != expected_functions:
            raise ValueError(f"Native CAN peer {case} lost exact pair pin functions")
        if any(
            observed.component_pin_numbers.get(reference) != ("1", "2")
            for reference in ("U1", "U2", "U3", "R1", *(("R2",) if case == "peer-fault" else ()))
        ):
            raise ValueError(f"Native CAN peer {case} lost a complete component pin inventory")
        expected_nets = (
            {"NET_A": {"U1.1", "U2.1", "U3.1", "R1.1"}, "NET_B": {"U1.2", "U2.2", "U3.2", "R1.2"}}
            if case == "peer-control"
            else {
                "NET_A": {"U1.1", "U2.1", "U3.1", "R1.1", "R2.1"},
                "NET_B": {"U1.2", "U2.2", "R1.2"},
                "NET_C": {"U3.2", "R2.2"},
            }
        )
        if {net: set(observed.nets.get(net, ())) for net in expected_nets} != expected_nets:
            raise ValueError(f"Native CAN peer {case} changed the expected net assignments")
        report = evaluate(
            f"synthetic-can-peer-{case}",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-can-peer-{case}",
                observed=observed,
                netlist_sha256=digest(output / f"{case}.first.netlist.xml"),
            ),
            DesignLintPolicy(),
        )
        matching = tuple(
            item for item in report.findings if item.rule_id == "bus.can_peer_assignment_divergence"
        )
        expected_status = "PASS" if case == "peer-control" else "REVIEW"
        expected_evidence = {
            "shared_role": ("CANH",),
            "shared_net": ("NET_A",),
            "complementary_role": ("CANL",),
            "complementary_nets": ("NET_B", "NET_C"),
            "participants": (
                "U1:U1.1=CANH/NET_A;U1.2=CANL/NET_B",
                "U2:U2.1=CANH/NET_A;U2.2=CANL/NET_B",
                "U3:U3.1=CANH/NET_A;U3.2=CANL/NET_C",
            ),
        }
        if (
            report.status != expected_status
            or len(report.findings) != len(matching)
            or len(matching) != (0 if case == "peer-control" else 1)
            or (case == "peer-fault" and matching[0].mode != "review")
            or (case == "peer-fault" and dict(matching[0].evidence) != expected_evidence)
        ):
            raise ValueError(f"Native CAN peer {case} no longer matches its lint control/fault")
        report_repeat = evaluate(
            f"synthetic-can-peer-{case}",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-can-peer-{case}",
                observed=observed_by_run["repeat"],
                netlist_sha256=digest(output / f"{case}.repeat.netlist.xml"),
            ),
            DesignLintPolicy(),
        )
        semantic_findings = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence) for item in report.findings
        )
        repeated_findings = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in report_repeat.findings
        )
        if semantic_findings != repeated_findings:
            raise ValueError(f"Native CAN peer {case} lint report is not repeatable")
        logs[case] = (
            report,
            matching,
            normalized_hashes["first"],
            erc_warning_types["first"],
        )

    for case in cases:
        report, findings, normalized_sha256, warning_types = logs[case]
        log.event(
            f"can-peer-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_sha256,
            lint_status=report.status,
            findings=";".join(item.rule_id for item in findings) or "none",
            erc_errors="0",
            erc_warning_types=";".join(warning_types) or "none",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_erc_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    log.event(
        "can-peer-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
