"""Power-sequence fixture analysis and native acceptance."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def power_sequence_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Repeat exact-version exports and check an authored PG-to-enable dependency."""
    import hashlib
    import json
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        NetlistContract,
        PowerSequenceDependencyRequirement,
        PowerSequenceEndpointRequirement,
        PowerSequenceMap,
        PowerSequenceStageRequirement,
    )
    from .hwrepo.power_sequences import (
        PowerSequenceObservedCycle,
        power_sequence_graph_has_cycle,
        power_sequence_mismatches,
        power_sequence_observed_enable_cycles,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Power-sequence fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/power-sequence-native"
    )
    cases = {
        "control": "control.kicad_sch",
        "open-enable": "open-enable.kicad_sch",
        "output-enable-cycle": "output-enable-cycle.kicad_sch",
    }
    fixtures = {case: fixture_root / filename for case, filename in cases.items()}
    source_hashes = {case: digest(path) for case, path in fixtures.items()}
    scratch = Path(
        tempfile.mkdtemp(prefix=f"power-sequence-{project}-", dir=log.directory.resolve())
    )
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    export_commands = "\n".join(
        f"for run in first repeat; do kicad-cli sch export netlist --format kicadxml "
        f'--output "/output/{case}.${{run}}.netlist.xml" '
        f'"/fixtures/{cases[case]}" || exit $?; done'
        for case in cases
    )
    source = "\n".join(
        (
            'mkdir -p "$HOME"',
            'actual="$(kicad-cli version)"',
            'printf "kicad_version=%s\\n" "$actual"',
            f'test "$actual" = "{config.kicad_version}"',
            export_commands,
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
        "HOME=/tmp/kicad-power-sequence-fixture",
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
        source,
    )
    stage = "power-sequence-fixture/native-export"
    log.event(stage, "START", project=project, kicad_version=config.kicad_version, image=pinned)
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            stage,
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native power-sequence fixture command failed: {command.stderr or command.error}"
        )

    sequence_map = PowerSequenceMap(
        basis="Synthetic datasheet startup table: upstream PG must drive downstream EN",
        stages=(
            PowerSequenceStageRequirement(
                id="rail-a",
                output=PowerSequenceEndpointRequirement(
                    reference="U1",
                    pin="U1.2",
                    symbol="Synthetic:Regulator",
                    footprint="Synthetic:SOT23-5",
                    net="RAIL_A",
                    part_id="SYNTH-REG-A",
                ),
                power_good=PowerSequenceEndpointRequirement(
                    reference="U1",
                    pin="U1.3",
                    symbol="Synthetic:Regulator",
                    footprint="Synthetic:SOT23-5",
                    net="GOOD_A",
                    part_id="SYNTH-REG-A",
                ),
                enable=PowerSequenceEndpointRequirement(
                    reference="U1",
                    pin="U1.1",
                    symbol="Synthetic:Regulator",
                    footprint="Synthetic:SOT23-5",
                    net="CONTROL_ON",
                    part_id="SYNTH-REG-A",
                ),
                enable_control="always_on",
                basis="Synthetic upstream regulator source page 3",
            ),
            PowerSequenceStageRequirement(
                id="rail-b",
                output=PowerSequenceEndpointRequirement(
                    reference="U2",
                    pin="U2.2",
                    symbol="Synthetic:Regulator",
                    footprint="Synthetic:SOT23-5",
                    net="RAIL_B",
                    part_id="SYNTH-REG-B",
                ),
                enable=PowerSequenceEndpointRequirement(
                    reference="U2",
                    pin="U2.1",
                    symbol="Synthetic:Regulator",
                    footprint="Synthetic:SOT23-5",
                    net="GOOD_A",
                    part_id="SYNTH-REG-B",
                ),
                enable_control="netlist",
                basis="Synthetic downstream regulator source page 5",
            ),
        ),
        dependencies=(
            PowerSequenceDependencyRequirement(
                id="rail-a-pg-before-rail-b-enable",
                predecessor_stage="rail-a",
                successor_stage="rail-b",
                signal_net="GOOD_A",
                basis="Synthetic source requirement: rail A power-good gates rail B enable",
            ),
        ),
    )
    if power_sequence_graph_has_cycle(sequence_map):
        raise ValueError("Synthetic power-sequence control map unexpectedly contains a cycle")

    def cycle_endpoint(
        reference: str, pin: str, net: str, part_id: str
    ) -> PowerSequenceEndpointRequirement:
        return PowerSequenceEndpointRequirement(
            reference=reference,
            pin=f"{reference}.{pin}",
            symbol="Synthetic:Regulator",
            footprint="Synthetic:SOT23-5",
            net=net,
            part_id=part_id,
        )

    cycle_sequence_map = PowerSequenceMap(
        basis="Synthetic source page 6, mapped stage endpoint table",
        stages=(
            PowerSequenceStageRequirement(
                id="rail-a",
                output=cycle_endpoint("U1", "2", "RAIL_A", "SYNTH-REG-A"),
                power_good=cycle_endpoint("U1", "3", "GOOD_A", "SYNTH-REG-A"),
                enable=cycle_endpoint("U1", "1", "RAIL_B", "SYNTH-REG-A"),
                enable_control="netlist",
                basis="Synthetic source identifies rail A stage endpoints",
            ),
            PowerSequenceStageRequirement(
                id="rail-b",
                output=cycle_endpoint("U2", "2", "RAIL_B", "SYNTH-REG-B"),
                power_good=cycle_endpoint("U2", "3", "GOOD_B", "SYNTH-REG-B"),
                enable=cycle_endpoint("U2", "1", "RAIL_A", "SYNTH-REG-B"),
                enable_control="netlist",
                basis="Synthetic source identifies rail B stage endpoints",
            ),
            PowerSequenceStageRequirement(
                id="rail-c",
                output=cycle_endpoint("U3", "2", "RAIL_C", "SYNTH-REG-C"),
                power_good=cycle_endpoint("U3", "3", "GOOD_C", "SYNTH-REG-C"),
                enable=cycle_endpoint("U3", "1", "GOOD_B", "SYNTH-REG-C"),
                enable_control="netlist",
                basis="Synthetic source identifies rail C stage endpoints",
            ),
        ),
        dependencies=(
            PowerSequenceDependencyRequirement(
                id="rail-b-before-rail-c",
                predecessor_stage="rail-b",
                successor_stage="rail-c",
                signal_net="GOOD_B",
                basis="Synthetic source requires rail B power-good to enable rail C",
            ),
        ),
    )
    if power_sequence_graph_has_cycle(cycle_sequence_map):
        raise ValueError("Synthetic output-to-enable map has a declared dependency cycle")
    sequence_maps = {
        "control": sequence_map,
        "open-enable": sequence_map,
        "output-enable-cycle": cycle_sequence_map,
    }

    parsed: dict[tuple[str, str], NetlistContract] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    normalized_hashes: dict[tuple[str, str], str] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native power-sequence export omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            parsed[(case, run)] = observed
            canonical = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(canonical).hexdigest()
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native {case} exports differ after canonical netlist normalization")

        if digest(fixtures[case]) != source_hashes[case]:
            raise ValueError(f"Synthetic {case} schematic changed during native export")

    expected_nets = {
        "control": {
            "U1.1": "CONTROL_ON",
            "U1.2": "RAIL_A",
            "U1.3": "GOOD_A",
            "U2.1": "GOOD_A",
            "U2.2": "RAIL_B",
            "U2.3": "GOOD_B",
        },
        "open-enable": {
            "U1.1": "CONTROL_ON",
            "U1.2": "RAIL_A",
            "U1.3": "GOOD_A",
            "U2.1": "FLOATING_ENABLE",
            "U2.2": "RAIL_B",
            "U2.3": "GOOD_B",
        },
        "output-enable-cycle": {
            "U1.1": "RAIL_B",
            "U1.2": "RAIL_A",
            "U1.3": "GOOD_A",
            "U2.1": "RAIL_A",
            "U2.2": "RAIL_B",
            "U2.3": "GOOD_B",
            "U3.1": "GOOD_B",
            "U3.2": "RAIL_C",
            "U3.3": "GOOD_C",
        },
    }
    expected_components = {
        "control": ("U1", "U2"),
        "open-enable": ("U1", "U2"),
        "output-enable-cycle": ("U1", "U2", "U3"),
    }
    reports: dict[str, DesignLintReport] = {}
    for case in cases:
        observed_cycles: tuple[PowerSequenceObservedCycle, ...] = ()
        observed_cycle_stages = "none"
        observed = parsed[(case, "first")]
        references = expected_components[case]
        for reference in references:
            if observed.component_symbols.get(reference) != "Synthetic:Regulator":
                raise ValueError(
                    f"Native {case} export lost {reference} synthetic regulator symbol identity"
                )
        for reference, suffix in zip(references, ("A", "B", "C"), strict=False):
            component = observed.components.get(reference)
            if (
                component is None
                or component.footprint != "Synthetic:SOT23-5"
                or component.part_id != f"SYNTH-REG-{suffix}"
                or set(observed.component_pin_numbers.get(reference, ())) != {"1", "2", "3"}
            ):
                raise ValueError(
                    f"Native {case} export changed {reference} identity or pin inventory"
                )
        for pin, net in expected_nets[case].items():
            assigned = tuple(
                sorted(candidate for candidate, pins in observed.nets.items() if pin in pins)
            )
            if assigned != (net,):
                raise ValueError(f"Native {case} export maps {pin} to {assigned!r}; expected {net}")
        case_sequence_map = sequence_maps[case]
        issues = power_sequence_mismatches(case_sequence_map, observed)
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=f"synthetic-power-sequence-{case}",
            observed=observed,
            netlist_sha256=raw_hashes[(case, "first")],
        )
        reports[case] = evaluate(
            f"synthetic-power-sequence-{case}",
            coach,
            DesignLintPolicy(power_sequence_map=case_sequence_map),
        )
        if case == "control" and (
            issues or reports[case].findings or reports[case].status != "PASS"
        ):
            raise ValueError("Native power-sequence control did not satisfy its authored map")
        if case == "open-enable":
            findings = tuple(
                finding
                for finding in reports[case].findings
                if finding.rule_id == "power.mapped_sequence_dependency_mismatch"
            )
            if (
                reports[case].status != "REVIEW"
                or len(findings) != 1
                or len(issues) != 1
                or not any(
                    "U2.1 is assigned to FLOATING_ENABLE" in issue for issue in issues[0].issues
                )
            ):
                raise ValueError("Native power-sequence open-enable fault was not localized")
        if case == "output-enable-cycle":
            observed_cycles = power_sequence_observed_enable_cycles(case_sequence_map, observed)
            cycle_findings = tuple(
                finding
                for finding in reports[case].findings
                if finding.rule_id == "power.mapped_sequence_dependency_mismatch"
            )
            if (
                power_sequence_graph_has_cycle(case_sequence_map)
                or issues
                or len(observed_cycles) != 1
                or observed_cycles[0].stage_ids != ("rail-a", "rail-b")
                or reports[case].status != "REVIEW"
                or len(cycle_findings) != 1
                or cycle_findings[0].evidence["observed_output_to_enable_cycle_stages"]
                != ("rail-a, rail-b",)
            ):
                raise ValueError("Native mapped output-to-enable cycle was not localized")
            observed_cycle_stages = ",".join(observed_cycles[0].stage_ids)
        log.event(
            f"power-sequence-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            lint_status=reports[case].status,
            power_sequence_findings=",".join(finding.rule_id for finding in reports[case].findings)
            or "none",
            observed_enable_net=expected_nets[case]["U2.1"],
            observed_enable_cycle_stages=observed_cycle_stages,
            repeatable="true",
        )
    log.event(
        stage,
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        repeatable="true",
        repeatability_basis="canonical_native_netlist",
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
