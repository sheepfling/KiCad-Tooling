"""Synthetic power-sequence contracts and reports shared by focused tests."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    PowerSequenceDependencyRequirement,
    PowerSequenceEndpointRequirement,
    PowerSequenceMap,
    PowerSequenceStageRequirement,
)

RULE_ID = "power.mapped_sequence_dependency_mismatch"


def power_sequence_map(*, cycle: bool = False, firmware_enable: bool = True) -> PowerSequenceMap:
    stage_one = PowerSequenceStageRequirement(
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
            net="GOOD_B" if cycle else "CONTROL_ON",
            part_id="SYNTH-REG-A",
        ),
        enable_control="netlist" if cycle else "always_on",
        basis="Synthetic upstream rail; independent requirement states this startup role",
    )
    stage_two = PowerSequenceStageRequirement(
        id="rail-b",
        output=PowerSequenceEndpointRequirement(
            reference="U2",
            pin="U2.2",
            symbol="Synthetic:Regulator",
            footprint="Synthetic:SOT23-5",
            net="RAIL_B",
            part_id="SYNTH-REG-B",
        ),
        power_good=(
            PowerSequenceEndpointRequirement(
                reference="U2",
                pin="U2.3",
                symbol="Synthetic:Regulator",
                footprint="Synthetic:SOT23-5",
                net="GOOD_B",
                part_id="SYNTH-REG-B",
            )
            if cycle
            else None
        ),
        enable=PowerSequenceEndpointRequirement(
            reference="U2",
            pin="U2.1",
            symbol="Synthetic:Regulator",
            footprint="Synthetic:SOT23-5",
            net="GOOD_A",
            part_id="SYNTH-REG-B",
        ),
        enable_control="firmware" if firmware_enable else "netlist",
        basis="Synthetic downstream rail with a mapped enable pin",
    )
    dependencies = [
        PowerSequenceDependencyRequirement(
            id="rail-a-before-rail-b",
            predecessor_stage="rail-a",
            successor_stage="rail-b",
            signal_net="GOOD_A",
            basis="Synthetic device requirement: rail A power-good drives rail B enable",
        )
    ]
    stages = [stage_one, stage_two]
    if cycle:
        dependencies.append(
            PowerSequenceDependencyRequirement(
                id="rail-b-before-rail-a",
                predecessor_stage="rail-b",
                successor_stage="rail-a",
                signal_net="GOOD_B",
                basis="Synthetic malformed source requirement closes a cycle",
            )
        )
    return PowerSequenceMap(
        basis="Synthetic source page 4, startup dependency table",
        stages=tuple(stages),
        dependencies=tuple(dependencies),
    )


def power_sequence_netlist(*, fault: str | None = None, cycle: bool = False) -> NetlistContract:
    components = {
        "U1": ComponentContract(
            value="Synthetic regulator A",
            footprint="Synthetic:SOT23-5",
            part_id="SYNTH-REG-A",
        ),
        "U2": ComponentContract(
            value="Synthetic regulator B",
            footprint="Synthetic:SOT23-5",
            part_id="SYNTH-REG-B",
        ),
    }
    symbols = {"U1": "Synthetic:Regulator", "U2": "Synthetic:Regulator"}
    pin_numbers = {"U1": ("1", "2", "3"), "U2": ("1", "2", "3")}
    nets: dict[str, tuple[str, ...]] = {
        "RAIL_A": ("U1.2",),
        "GOOD_A": ("U1.3", "U2.1"),
        "RAIL_B": ("U2.2",),
        "CONTROL_ON": ("U1.1",),
    }
    dnp: tuple[str, ...] = ()
    if cycle:
        nets.pop("CONTROL_ON")
        nets["GOOD_B"] = ("U2.3", "U1.1")
    if fault == "open-enable":
        nets["GOOD_A"] = ("U1.3",)
        nets["FLOATING"] = ("U2.1",)
    elif fault == "wrong-output":
        nets["RAIL_A"] = ()
        nets["OTHER_RAIL"] = ("U1.2",)
    elif fault == "wrong-symbol":
        symbols["U1"] = "Synthetic:Switch"
    elif fault == "wrong-part-id":
        components["U1"] = components["U1"].model_copy(update={"part_id": "WRONG-PART"})
    elif fault == "missing-pin":
        pin_numbers["U2"] = ("2", "3")
    elif fault == "dnp":
        dnp = ("U2",)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
    )


def power_sequence_output_cycle_map(*, cycle: bool) -> PowerSequenceMap:
    def endpoint(
        reference: str,
        pin: str,
        net: str,
        part_id: str,
    ) -> PowerSequenceEndpointRequirement:
        return PowerSequenceEndpointRequirement(
            reference=reference,
            pin=f"{reference}.{pin}",
            symbol="Synthetic:Regulator",
            footprint="Synthetic:SOT23-5",
            net=net,
            part_id=part_id,
        )

    stages = (
        PowerSequenceStageRequirement(
            id="rail-a",
            output=endpoint("U1", "2", "RAIL_A", "SYNTH-REG-A"),
            power_good=endpoint("U1", "3", "GOOD_A", "SYNTH-REG-A"),
            enable=endpoint("U1", "1", "RAIL_B" if cycle else "CONTROL_ON", "SYNTH-REG-A"),
            enable_control="netlist" if cycle else "external",
            basis="Synthetic source identifies rail A stage endpoints",
        ),
        PowerSequenceStageRequirement(
            id="rail-b",
            output=endpoint("U2", "2", "RAIL_B", "SYNTH-REG-B"),
            power_good=endpoint("U2", "3", "GOOD_B", "SYNTH-REG-B"),
            enable=endpoint("U2", "1", "RAIL_A", "SYNTH-REG-B"),
            enable_control="netlist",
            basis="Synthetic source identifies rail B stage endpoints",
        ),
        PowerSequenceStageRequirement(
            id="rail-c",
            output=endpoint("U3", "2", "RAIL_C", "SYNTH-REG-C"),
            power_good=endpoint("U3", "3", "GOOD_C", "SYNTH-REG-C"),
            enable=endpoint("U3", "1", "GOOD_B", "SYNTH-REG-C"),
            enable_control="netlist",
            basis="Synthetic source identifies rail C stage endpoints",
        ),
    )
    return PowerSequenceMap(
        basis="Synthetic source page 6, mapped stage endpoint table",
        stages=stages,
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


def power_sequence_output_cycle_netlist(*, cycle: bool) -> NetlistContract:
    components = {
        reference: ComponentContract(
            value=f"Synthetic regulator {suffix}",
            footprint="Synthetic:SOT23-5",
            part_id=f"SYNTH-REG-{suffix}",
        )
        for reference, suffix in (("U1", "A"), ("U2", "B"), ("U3", "C"))
    }
    return NetlistContract(
        components=components,
        nets={
            "RAIL_A": ("U1.2", "U2.1"),
            "RAIL_B": ("U1.1", "U2.2") if cycle else ("U2.2",),
            "GOOD_A": ("U1.3",),
            "GOOD_B": ("U2.3", "U3.1"),
            "RAIL_C": ("U3.2",),
            "GOOD_C": ("U3.3",),
            "CONTROL_ON": () if cycle else ("U1.1",),
        },
        component_symbols={reference: "Synthetic:Regulator" for reference in components},
        component_pin_numbers={reference: ("1", "2", "3") for reference in components},
    )


def lint_report(
    netlist: NetlistContract,
    sequence_map: PowerSequenceMap | None = None,
    *,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-power-sequence",
        observed=netlist,
        netlist_sha256=hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest(),
    )
    return evaluate(
        "synthetic-power-sequence",
        coach,
        DesignLintPolicy(
            power_sequence_map=sequence_map,
            rules=() if override is None else (override,),
            ignores=() if ignore is None else (ignore,),
        ),
    )
