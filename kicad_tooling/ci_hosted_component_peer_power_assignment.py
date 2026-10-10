"""Hosted native component peer power-assignment fixture lane."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def component_peer_power_assignment_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify shared-PART_ID power and return assignment review on pinned exports."""
    import hashlib
    import json
    import os
    import tempfile

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
        raise ValueError(
            f"Peer power-assignment fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/design_lint/component-peer-power-assignment-native"
    )
    cases = {"fault": "fault.kicad_sch", "control": "control.kicad_sch"}
    source_hashes = {case: digest(fixture_root / filename) for case, filename in cases.items()}
    expected_source_hashes = {
        "fault": "2e4bc0c9f883e948660b1982a7ccae888c18c3b52b9ae285b878666a7353c4c6",
        "control": "23fec400e1e0a0581abc650a7d108512948d5d0b14744a276ebabc75a94be67d",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("Synthetic peer power-assignment fixture source digest changed")
    scratch = Path(
        tempfile.mkdtemp(prefix=f"peer-power-assignment-{project}-", dir=log.directory.resolve())
    )
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    commands = [
        'mkdir -p "$HOME"\n',
        'actual="$(kicad-cli version)"\n',
        'printf "kicad_version=%s\\n" "$actual"\n',
        f'test "$actual" = "{config.kicad_version}"\n',
    ]
    for case, filename in cases.items():
        commands.extend(
            (
                f'printf "exporting_fixture=%s\\n" "{filename}"\n',
                (
                    f"for run in first repeat; do kicad-cli sch export netlist "
                    f'--format kicadxml --output "/output/{case}.${{run}}.netlist.xml" '
                    f'"/fixtures/{filename}"; done\n'
                ),
            )
        )
    command = (
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
        f"HOME=/tmp/kicad-peer-power-assignment-{project}",
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
        "".join(commands),
    )
    lane = "component-peer-power-assignment-fixture"
    log.event(
        f"{lane}/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    result = run_command(root, command, timeout=600)
    write_model(scratch / "native.command.json", result)
    if result.returncode != 0 or result.error is not None:
        log.event(
            f"{lane}/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=result.stderr or result.error or f"exit {result.returncode}",
        )
        raise ValueError(
            f"Native peer power-assignment fixture command failed: {result.stderr or result.error}"
        )
    log.event(
        f"{lane}/native-export",
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
    expected_assignments = {
        "fault": {
            "U1.1": ("SYNTHETIC_NET_A",),
            "U2.1": ("SYNTHETIC_NET_B",),
            "U1.2": ("SYNTHETIC_NET_C",),
            "U2.2": ("SYNTHETIC_NET_D",),
        },
        "control": {
            "U1.1": ("SYNTHETIC_NET_1",),
            "U2.1": ("SYNTHETIC_NET_1",),
            "U1.2": ("SYNTHETIC_NET_2",),
            "U2.2": ("SYNTHETIC_NET_2",),
        },
    }
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native peer power-assignment export omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            actual_assignments = {
                pin: tuple(sorted(net for net, pins in observed.nets.items() if pin in pins))
                for pin in expected_assignments[case]
            }
            if actual_assignments != expected_assignments[case]:
                raise ValueError(
                    f"Native {case} expected pin assignments {expected_assignments[case]}, "
                    f"observed {actual_assignments}"
                )
            expected_components = {
                "U1": ("Synthetic:PowerModule", "SYNTHETIC-POWER-MODULE-001"),
                "U2": ("Synthetic:PowerModuleAlias", "SYNTHETIC-POWER-MODULE-001"),
            }
            if set(observed.components) != set(expected_components):
                raise ValueError(f"Native {case} export omitted the fitted peer components")
            for reference, (symbol, part_id) in expected_components.items():
                component = observed.components[reference]
                if (
                    observed.component_symbols.get(reference) != symbol
                    or component.part_id != part_id
                    or component.value != "Synthetic power module"
                    or component.footprint != "Synthetic:Module"
                    or observed.component_pin_numbers.get(reference) != ("1", "2")
                ):
                    raise ValueError(
                        f"Native {case} export omitted the exact shared-PART_ID identity "
                        f"for {reference}"
                    )
                if any(
                    observed.pin_functions.get(f"{reference}.{number}") != function
                    or observed.pin_electrical_types.get(f"{reference}.{number}") != "power_in"
                    for number, function in (("1", "VDD"), ("2", "GND"))
                ):
                    raise ValueError(
                        f"Native {case} export omitted matching power/return pin metadata "
                        f"for {reference}"
                    )
            serialized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(serialized).hexdigest()
            project_id = f"synthetic-peer-power-assignment-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, DesignLintPolicy())
            findings = tuple(
                item
                for item in reports[(case, run)].findings
                if item.rule_id == "component.peer_power_pin_assignment_divergence"
            )
            decoupling_findings = tuple(
                item
                for item in reports[(case, run)].findings
                if item.rule_id == "power.ic_rail_without_fitted_capacitor"
            )
            expected_roles: set[str] = {"ground/return", "supply"} if case == "fault" else set()
            actual_roles = {item.evidence["peer_role"][0] for item in findings}
            expected_decoupling_nets = (
                {"SYNTHETIC_NET_A", "SYNTHETIC_NET_B"} if case == "fault" else {"SYNTHETIC_NET_1"}
            )
            actual_decoupling_nets = {item.evidence["net"][0] for item in decoupling_findings}
            expected_rules = {"power.ic_rail_without_fitted_capacitor"}
            if case == "fault":
                expected_rules.add("component.peer_power_pin_assignment_divergence")
            actual_rules = {item.rule_id for item in reports[(case, run)].findings}
            expected_status = "REVIEW"
            if (
                actual_roles != expected_roles
                or actual_decoupling_nets != expected_decoupling_nets
                or actual_rules != expected_rules
                or reports[(case, run)].status != expected_status
            ):
                raise ValueError(
                    f"Native {case} expected peer power roles {sorted(expected_roles)} and "
                    f"decoupling nets {sorted(expected_decoupling_nets)}, rules "
                    f"{sorted(expected_rules)}, status {expected_status}; observed "
                    f"roles {sorted(actual_roles)}, decoupling nets "
                    f"{sorted(actual_decoupling_nets)}, rules {sorted(actual_rules)}, "
                    f"status {reports[(case, run)].status}"
                )
            if case == "fault" and any(
                item.evidence.get("peer_identity_basis") != ("part_id",)
                or item.evidence.get("peer_identity") != ("SYNTHETIC-POWER-MODULE-001",)
                for item in findings
            ):
                raise ValueError("Native fault omitted its shared PART_ID identity evidence")
    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")] for case in cases
    ):
        raise ValueError("Native peer power-assignment exports differ after normalization")

    for case, filename in cases.items():
        findings = tuple(
            item
            for item in reports[(case, "first")].findings
            if item.rule_id == "component.peer_power_pin_assignment_divergence"
        )
        log.event(
            f"{lane}/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            lint_status=reports[(case, "first")].status,
            peer_power_findings=";".join(sorted(item.evidence["peer_role"][0] for item in findings))
            or "none",
            independent_decoupling_findings=";".join(
                sorted(
                    item.evidence["net"][0]
                    for item in reports[(case, "first")].findings
                    if item.rule_id == "power.ic_rail_without_fitted_capacitor"
                )
            )
            or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    if any(
        digest(fixture_root / filename) != source_hashes[case] for case, filename in cases.items()
    ):
        raise ValueError("Synthetic peer power-assignment fixture changed during native export")
