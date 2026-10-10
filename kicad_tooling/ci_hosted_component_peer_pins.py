"""Hosted native component peer pin fixture lane."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def component_peer_power_output_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify the peer power-output regression pair on pinned KiCad exports."""
    _component_peer_pin_assignment_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        kind="power-output",
    )


def component_peer_signal_output_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify the peer signal-output regression pair on pinned KiCad exports."""
    _component_peer_pin_assignment_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        kind="signal-output",
    )


def component_peer_signal_input_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify the peer signal-input regression pair on pinned KiCad exports."""
    _component_peer_pin_assignment_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        kind="signal-input",
    )


def component_peer_bidirectional_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify the peer bidirectional-pin regression pair on pinned KiCad exports."""
    _component_peer_pin_assignment_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        kind="bidirectional",
    )


def _component_peer_pin_assignment_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
    kind: Literal["power-output", "signal-output", "signal-input", "bidirectional"],
) -> None:
    """Verify one comparable-peer open-pin class against repeated KiCad exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy, DesignLintReport
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Peer {kind} fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1]
        / f"tests/fixtures/design_lint/component-peer-{kind}-native"
    )
    native_pin_types = {
        "power-output": "power_out",
        "signal-output": "output",
        "signal-input": "input",
        "bidirectional": "bidirectional",
    }
    rule_ids = {
        "power-output": "component.peer_power_output_unconnected",
        "signal-output": "component.peer_signal_output_unconnected",
        "signal-input": "component.peer_signal_input_unconnected",
        "bidirectional": "component.peer_bidirectional_pin_unconnected",
    }
    fixture_symbols = {
        "power-output": "Synthetic:PowerModule",
        "signal-output": "Synthetic:SignalModule",
        "signal-input": "Synthetic:SignalInputModule",
        "bidirectional": "Synthetic:BidirectionalModule",
    }
    functions = {
        "power-output": "Pin_2",
        "signal-output": "OUT",
        "signal-input": "IN",
        "bidirectional": "DATA_IO",
    }
    native_pin_type = native_pin_types[kind]
    rule_id = rule_ids[kind]
    fixture_symbol = fixture_symbols[kind]
    pin_function = functions[kind]
    signal_name = {
        "signal-input": "INPUT",
        "bidirectional": "DATA_IO",
        "power-output": "VOUT",
        "signal-output": "VOUT",
    }[kind]
    lane_name = f"component-peer-{kind}-fixture"
    display_name = kind
    cases = {
        "fault": ("fault.kicad_sch", ("U2.2",)),
        "control": ("control.kicad_sch", ()),
    }
    source_hashes = {case: digest(fixture_root / filename) for case, (filename, _) in cases.items()}
    scratch = Path(
        tempfile.mkdtemp(prefix=f"peer-{kind}-output-{project}-", dir=log.directory.resolve())
    )
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
    for case, (filename, _) in cases.items():
        source_lines.extend(
            (
                f'printf "exporting_fixture=%s\\n" "{filename}"\n',
                (
                    f"for run in first repeat; do kicad-cli sch export netlist "
                    f'--format kicadxml --output "/output/{case}.${{run}}.netlist.xml" '
                    f'"/fixtures/{filename}"; done\n'
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
        f"HOME=/tmp/kicad-peer-{kind}-output-fixtures",
        "-v",
        f"{fixture_root.resolve()}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        "".join(source_lines),
    )
    log.event(
        f"{lane_name}/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            f"{lane_name}/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native peer {display_name} fixture command failed: {command.stderr or command.error}"
        )
    log.event(
        f"{lane_name}/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    for case, (_, expected_unassigned) in cases.items():
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native peer {display_name} fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            expected_assignments = (
                {"U1.2": (signal_name,), "U2.2": ()}
                if case == "fault"
                else {"U1.2": (f"{signal_name}_A",), "U2.2": (f"{signal_name}_B",)}
            )
            actual_assignments = {
                pin: tuple(sorted(net for net, pins in observed.nets.items() if pin in pins))
                for pin in expected_assignments
            }
            if actual_assignments != expected_assignments:
                raise ValueError(
                    f"Native {case} expected schematic output assignments "
                    f"{expected_assignments}, observed {actual_assignments}"
                )
            expected_symbols = (
                {"U1": "Synthetic:PowerModule", "U2": "Synthetic:PowerModuleAlias"}
                if kind == "power-output"
                else {"U1": fixture_symbol, "U2": fixture_symbol}
            )
            if (
                observed.component_symbols != expected_symbols
                or observed.component_pin_numbers.get("U1") != ("1", "2")
                or observed.component_pin_numbers.get("U2") != ("1", "2")
                or observed.pin_electrical_types.get("U1.2") != native_pin_type
                or observed.pin_electrical_types.get("U2.2") != native_pin_type
                or observed.pin_functions.get("U1.2") != pin_function
                or observed.pin_functions.get("U2.2") != pin_function
            ):
                raise ValueError(
                    f"Native {case} export omitted the exact peer symbol, pin inventory, "
                    f"or native {native_pin_type} pin types and {pin_function} functions"
                )
            if kind == "power-output" and {
                reference: component.part_id for reference, component in observed.components.items()
            } != {
                "U1": "SYNTHETIC-POWER-MODULE-001",
                "U2": "SYNTHETIC-POWER-MODULE-001",
            }:
                raise ValueError(f"Native {case} export omitted the matching PART_ID fields")
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            project_id = f"synthetic-peer-{kind}-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, DesignLintPolicy())
            findings = tuple(
                item for item in reports[(case, run)].findings if item.rule_id == rule_id
            )
            actual_unassigned = findings[0].evidence.get("unassigned_pins", ()) if findings else ()
            expected_finding_count = 1 if expected_unassigned else 0
            if actual_unassigned != expected_unassigned or len(findings) != expected_finding_count:
                raise ValueError(
                    f"Native {case} expected peer {display_name} pins {expected_unassigned}, "
                    f"observed {actual_unassigned}"
                )
            expected_status = "REVIEW" if expected_unassigned else "PASS"
            if reports[(case, run)].status != expected_status:
                raise ValueError(
                    f"Native {case} expected lint status {expected_status}, "
                    f"observed {reports[(case, run)].status}"
                )
            coverage = next(
                item
                for item in reports[(case, run)].component_peer_pin_coverage
                if item.rule_id == rule_id
            )
            expected_symbol_groups = 0 if kind == "power-output" else 1
            expected_part_id_groups = 1 if kind == "power-output" else 0
            if (
                coverage.status != "EVALUATED"
                or coverage.mode != "review"
                or coverage.netlist_sha256 != raw_hashes[(case, run)]
                or coverage.exact_symbol_peer_group_count != expected_symbol_groups
                or coverage.part_id_peer_group_count != expected_part_id_groups
                or coverage.candidate_group_count != expected_finding_count
                or coverage.deduplicated_candidate_group_count != 0
                or coverage.finding_count != expected_finding_count
                or coverage.suppressed_candidate_count != 0
            ):
                raise ValueError(
                    f"Native {case} component peer-pin coverage did not match the "
                    f"source-bound {rule_id} fault/control expectation"
                )

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")] for case in cases
    ):
        raise ValueError(
            f"Native peer {display_name} exports differ after normalization to parsed contracts"
        )
    for case, (filename, expected_unassigned) in cases.items():
        report = reports[(case, "first")]
        findings = tuple(item for item in report.findings if item.rule_id == rule_id)
        coverage = next(
            item for item in report.component_peer_pin_coverage if item.rule_id == rule_id
        )
        log.event(
            f"{lane_name}/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            lint_status=report.status,
            unassigned_pins=",".join(expected_unassigned) or "none",
            finding_count=len(findings),
            peer_coverage_status=coverage.status,
            peer_coverage_netlist_sha256=coverage.netlist_sha256,
            peer_coverage_exact_symbol_group_count=coverage.exact_symbol_peer_group_count,
            peer_coverage_part_id_group_count=coverage.part_id_peer_group_count,
            peer_coverage_candidate_count=coverage.candidate_group_count,
            peer_coverage_deduplicated_candidate_count=(
                coverage.deduplicated_candidate_group_count
            ),
            peer_coverage_finding_count=coverage.finding_count,
            peer_coverage_suppressed_count=coverage.suppressed_candidate_count,
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    if any(
        digest(fixture_root / filename) != source_hashes[case]
        for case, (filename, _) in cases.items()
    ):
        raise ValueError(
            f"Synthetic peer {display_name} fixture source changed during native export"
        )
