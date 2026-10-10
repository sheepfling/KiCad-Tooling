"""Hosted native serial peer fixture lane."""

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


def serial_peer_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Verify serial-peer coverage prompts against repeated pinned native exports."""
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
        SerialPeerAnalysis,
    )
    from .hwrepo.serial_participants import SerialPeerRosterContext
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
    fixture = fixture_root / "endpoints.kicad_sch"
    source_hash = digest(fixture)
    scratch = Path(tempfile.mkdtemp(prefix=f"serial-peer-{project}-", dir=log.directory.resolve()))
    inputs = scratch / "input"
    inputs.mkdir()
    source = inputs / "endpoints.kicad_sch"
    shutil.copyfile(fixture, source)
    if digest(source) != source_hash:
        raise ValueError("Synthetic serial-peer fixture changed while preparing native input")
    map_fixtures = {
        "partial": fixture_root / "peer-map-partial.json",
        "complete": fixture_root / "peer-map-complete.json",
    }
    map_source_hashes = {case: digest(path) for case, path in map_fixtures.items()}
    map_inputs = {case: inputs / path.name for case, path in map_fixtures.items()}
    for case, path in map_fixtures.items():
        shutil.copyfile(path, map_inputs[case])
        if digest(map_inputs[case]) != map_source_hashes[case]:
            raise ValueError(f"Synthetic serial-peer {case} map changed while preparing input")
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
        '    --output "/output/endpoints.${run}.netlist.xml" '
        '    "/fixtures/endpoints.kicad_sch"\n'
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
        "HOME=/tmp/kicad-serial-peer-fixtures",
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
        "serial-peer-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "serial-peer-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native serial-peer fixture command failed: {command.stderr or command.error}"
        )

    if (
        digest(fixture) != source_hash
        or digest(source) != source_hash
        or any(
            digest(map_fixtures[case]) != map_source_hashes[case]
            or digest(map_inputs[case]) != map_source_hashes[case]
            for case in map_fixtures
        )
    ):
        raise ValueError("Synthetic serial-peer fixture source changed during native export")
    contracts: dict[str, NetlistContract] = {}
    hashes: dict[str, str] = {}
    normalized_hashes: dict[str, str] = {}
    for run in ("first", "repeat"):
        path = output / f"endpoints.{run}.netlist.xml"
        if not path.is_file():
            raise ValueError(f"Native serial-peer fixture omitted {path.name}")
        hashes[run] = digest(path)
        contracts[run] = read_netlist(path)
        normalized = json.dumps(
            contracts[run].model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        normalized_hashes[run] = hashlib.sha256(normalized).hexdigest()
    if normalized_hashes["first"] != normalized_hashes["repeat"]:
        raise ValueError("Native serial-peer exports differ after typed-netlist normalization")

    observed = contracts["first"]
    expected_functions = {
        f"J{reference}.{pin}": function
        for reference in range(1, 5)
        for pin, function in ((1, "TX"), (2, "RX"))
    }
    if observed.pin_functions != expected_functions:
        raise ValueError(
            "Native serial-peer netlist changed the exact endpoint function inventory: "
            f"{observed.pin_functions}"
        )
    if observed.component_symbols != {
        f"J{reference}": "Synthetic:UART_Endpoint" for reference in range(1, 5)
    }:
        raise ValueError("Native serial-peer netlist changed synthetic connector identities")
    if observed.component_pin_numbers != {f"J{reference}": ("1", "2") for reference in range(1, 5)}:
        raise ValueError("Native serial-peer netlist changed the full connector pin inventory")
    expected_nets = {
        "SERIAL_A_TX": {"J1.1", "J2.2"},
        "SERIAL_A_RX": {"J1.2", "J2.1"},
        "SERIAL_B_TX": {"J3.1", "J4.2"},
        "SERIAL_B_RX": {"J3.2", "J4.1"},
    }
    actual_nets = {
        net: set(pins) for net, pins in observed.nets.items() if net.startswith("SERIAL_")
    }
    if actual_nets != expected_nets:
        raise ValueError(f"Native serial-peer netlist changed connector assignments: {actual_nets}")

    cases: dict[str, SerialPeerRosterContext] = {
        "unrostered": SerialPeerRosterContext(state="not_configured"),
    }
    for case, path in map_inputs.items():
        analysis = read_model(path, SerialPeerAnalysis)
        cases[case] = SerialPeerRosterContext(
            state="required",
            analysis=analysis,
            source_path=map_fixtures[case].relative_to(repository).as_posix(),
            source_sha256=map_source_hashes[case],
        )
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="connector.repeated_pin_function",
                mode="off",
                reason="Isolate synthetic serial-peer map coverage from repeated connector functions.",
            ),
        )
    )
    reports: dict[str, DesignLintReport] = {}
    for case, roster in cases.items():
        report_runs: list[DesignLintReport] = []
        for run in ("first", "repeat"):
            project_id = f"synthetic-serial-peer-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=contracts[run],
                netlist_sha256=hashes[run],
            )
            report_runs.append(evaluate(project_id, coach, policy, serial_peer_roster=roster))
        first, repeated = report_runs
        first_signature = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.disposition, item.evidence)
            for item in first.findings
        )
        repeat_signature = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.disposition, item.evidence)
            for item in repeated.findings
        )
        if first.status != repeated.status or first_signature != repeat_signature:
            raise ValueError(f"Native serial-peer {case} review changed on repeated export")
        reports[case] = first

    expected: dict[str, tuple[str, set[str]]] = {
        "unrostered": ("REVIEW", {"J1", "J2", "J3", "J4"}),
        "partial": ("REVIEW", {"J3", "J4"}),
        "complete": ("PASS", set()),
    }
    for case, (status, references) in expected.items():
        report = reports[case]
        findings = tuple(
            item for item in report.findings if item.rule_id == "bus.serial_unmapped_peer"
        )
        if (
            report.status != status
            or {item.subject.split(":", 1)[0] for item in findings} != references
        ):
            raise ValueError(
                f"Native serial-peer {case} case no longer matches expected coverage: "
                f"status={report.status}; findings="
                f"{[(item.rule_id, item.subject, item.mode) for item in report.findings]}"
            )
        if any(item.mode != "review" for item in findings):
            raise ValueError("Serial peer coverage heuristic no longer defaults to REVIEW")
        if case == "partial" and any(
            item.evidence["serial_peer_map_state"] != ("required",) for item in findings
        ):
            raise ValueError("Native serial-peer findings lost authored-map state evidence")
        log.event(
            f"serial-peer-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hash,
            netlist_sha256=hashes["first"],
            repeat_netlist_sha256=hashes["repeat"],
            normalized_netlist_sha256=normalized_hashes["first"],
            repeat_normalized_netlist_sha256=normalized_hashes["repeat"],
            lint_status=report.status,
            findings=";".join(item.subject for item in findings) or "none",
            authored_map_sha256=cases[case].source_sha256 or "none",
            pin_functions=";".join(
                f"{pin}={function}" for pin, function in sorted(observed.pin_functions.items())
            ),
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    log.event(
        "serial-peer-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_sha256=source_hash,
        netlist_sha256=hashes["first"],
        repeat_netlist_sha256=hashes["repeat"],
        normalized_netlist_sha256=normalized_hashes["first"],
        repeat_normalized_netlist_sha256=normalized_hashes["repeat"],
        repeatable="true",
        repeatability_basis="normalized_native_netlist_contract",
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
