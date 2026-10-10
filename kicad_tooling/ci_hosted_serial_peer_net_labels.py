"""Hosted native serial peer net-label fixture lane."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def serial_peer_net_label_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify UART net-label discovery for MCU alternate-function pins on native exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.contracts import read_model
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        DesignLintRuleOverride,
        NetlistContract,
    )
    from .hwrepo.serial_participants import SerialPeerRosterContext
    from .hwrepo.serial_peer_models import SerialPeerAnalysis
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Serial peer fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    repository = Path(__file__).resolve().parents[1]
    fixture_root = repository / "tests/fixtures/design_lint/serial-peer-native"
    fixture = fixture_root / "alternate-function-endpoint.kicad_sch"
    fixture_hash = digest(fixture)
    map_fixture = fixture_root / "peer-map-alternate-function.json"
    map_hash = digest(map_fixture)
    scratch = Path(
        tempfile.mkdtemp(prefix=f"serial-peer-net-label-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    source = inputs / fixture.name
    map_input = inputs / map_fixture.name
    shutil.copyfile(fixture, source)
    shutil.copyfile(map_fixture, map_input)
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
        "for run in first repeat; do\n"
        "  kicad-cli sch export netlist --format kicadxml "
        '    --output "/output/alternate.${run}.netlist.xml" '
        '    "/fixtures/alternate-function-endpoint.kicad_sch"\n'
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
        "HOME=/tmp/kicad-serial-net-label-fixtures",
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
        "serial-peer-net-label-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "serial-peer-net-label-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native serial-peer net-label fixture failed: {command.stderr or command.error}"
        )
    if (
        digest(fixture) != fixture_hash
        or digest(source) != fixture_hash
        or digest(map_fixture) != map_hash
        or digest(map_input) != map_hash
    ):
        raise ValueError("Synthetic serial-peer net-label fixture changed during native export")

    contracts: dict[str, NetlistContract] = {}
    netlist_hashes: dict[str, str] = {}
    normalized_hashes: dict[str, str] = {}
    for run in ("first", "repeat"):
        path = output / f"alternate.{run}.netlist.xml"
        if not path.is_file():
            raise ValueError(f"Native serial-peer net-label export omitted {path.name}")
        netlist_hashes[run] = digest(path)
        contracts[run] = read_netlist(path)
        normalized = json.dumps(
            contracts[run].model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        normalized_hashes[run] = hashlib.sha256(normalized).hexdigest()
    if normalized_hashes["first"] != normalized_hashes["repeat"]:
        raise ValueError("Alternate-function UART native exports differ after normalization")
    observed = contracts["first"]
    expected_functions = {
        "U1.1": "PA2",
        "U1.2": "PA3",
        "J5.1": "Pin_1",
        "J5.2": "Pin_2",
    }
    if observed.pin_functions != expected_functions:
        raise ValueError(
            "Alternate-function UART fixture changed its exact pin-function inventory: "
            f"{observed.pin_functions}"
        )
    if observed.nets != {
        "UART_RX": ("J5.2", "U1.2"),
        "UART_TX": ("J5.1", "U1.1"),
    }:
        raise ValueError(f"Alternate-function UART fixture changed native nets: {observed.nets}")

    analysis = read_model(map_input, SerialPeerAnalysis)
    mapped_roster = SerialPeerRosterContext(
        state="required",
        analysis=analysis,
        source_path=map_fixture.relative_to(repository).as_posix(),
        source_sha256=map_hash,
    )
    rosters = {
        "unrostered": SerialPeerRosterContext(state="not_configured"),
        "mapped": mapped_roster,
    }
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="connector.repeated_pin_function",
                mode="off",
                reason="Keep the alternate-function UART fixture focused on serial-map discovery.",
            ),
        )
    )
    for case, roster in rosters.items():
        repeated_reports: list[DesignLintReport] = []
        for run in ("first", "repeat"):
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-serial-net-label-{case}",
                observed=contracts[run],
                netlist_sha256=netlist_hashes[run],
            )
            repeated_reports.append(
                evaluate(
                    f"synthetic-serial-net-label-{case}", coach, policy, serial_peer_roster=roster
                )
            )
        first, repeated = repeated_reports

        def report_signature(report: DesignLintReport) -> tuple[tuple[object, ...], ...]:
            return tuple(
                (item.fingerprint, item.rule_id, item.mode, item.disposition, item.evidence)
                for item in report.findings
            )

        if first.status != repeated.status or report_signature(first) != report_signature(repeated):
            raise ValueError(f"Alternate-function serial-map {case} report is not repeatable")
        findings = tuple(
            item for item in first.findings if item.rule_id == "bus.serial_unmapped_peer"
        )
        expected = ("REVIEW", 1, "net_label") if case == "unrostered" else ("PASS", 0, None)
        actual_basis = findings[0].evidence.get("discovery_basis", (None,))[0] if findings else None
        if (first.status, len(findings), actual_basis) != expected:
            raise ValueError(
                f"Alternate-function serial-map {case} result changed: "
                f"status={first.status}; findings={findings}"
            )
        if (
            findings
            and "does not assert that a peer or connection is required" not in findings[0].message
        ):
            raise ValueError("UART net-label finding no longer states its review-only boundary")
        log.event(
            f"serial-peer-net-label-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=fixture_hash,
            netlist_sha256=netlist_hashes["first"],
            repeat_netlist_sha256=netlist_hashes["repeat"],
            normalized_netlist_sha256=normalized_hashes["first"],
            repeat_normalized_netlist_sha256=normalized_hashes["repeat"],
            lint_status=first.status,
            findings=";".join(item.subject for item in findings) or "none",
            discovery_basis=actual_basis or "none",
            authored_map_sha256=roster.source_sha256 or "none",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    log.event(
        "serial-peer-net-label-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_sha256=fixture_hash,
        netlist_sha256=netlist_hashes["first"],
        repeat_netlist_sha256=netlist_hashes["repeat"],
        normalized_netlist_sha256=normalized_hashes["first"],
        repeat_normalized_netlist_sha256=normalized_hashes["repeat"],
        pin_functions=";".join(
            f"{pin}={function}" for pin, function in sorted(observed.pin_functions.items())
        ),
        repeatable="true",
        repeatability_basis="normalized_native_netlist_contract",
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
