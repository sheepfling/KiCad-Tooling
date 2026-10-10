"""Synthetic helpers for component peer-pin lint regressions."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    NetlistContract,
)

RULE_ID = "component.peer_power_output_unconnected"
SIGNAL_RULE_ID = "component.peer_signal_output_unconnected"
INPUT_RULE_ID = "component.peer_signal_input_unconnected"
BIDIRECTIONAL_RULE_ID = "component.peer_bidirectional_pin_unconnected"


def peer_component_pin_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2"),
    pin_nets: tuple[str | None, ...] = ("VOUT", None),
    dnp: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
    default_symbol: str = "Synthetic:PowerModule",
    pin_electrical_types: tuple[str, ...] | None = None,
    pin_function: str = "OUT",
    pin_functions: tuple[str | None, ...] | None = None,
    missing_inventory: tuple[str, ...] = (),
    ambiguous_pins: tuple[str, ...] = (),
    part_ids: dict[str, str] | None = None,
    values: dict[str, str] | None = None,
    footprints: dict[str, str] | None = None,
) -> NetlistContract:
    if len(references) != len(pin_nets):
        raise ValueError("Each peer needs one pin-net case")
    symbols = symbols or {reference: default_symbol for reference in references}
    pin_electrical_types = pin_electrical_types or tuple("power_out" for _ in references)
    pin_functions = pin_functions or tuple(pin_function for _ in references)
    if len(pin_electrical_types) != len(references) or len(pin_functions) != len(references):
        raise ValueError("Each peer needs one pin type and function case")
    part_ids = part_ids or {}
    values = values or {}
    footprints = footprints or {}
    components = {
        reference: ComponentContract(
            value=values.get(reference, "Synthetic module"),
            footprint=footprints.get(reference, "Synthetic:Module"),
            part_id=part_ids.get(reference),
        )
        for reference in references
    }
    nets: dict[str, tuple[str, ...]] = {"DATA": tuple(f"{reference}.1" for reference in references)}
    for reference, net in zip(references, pin_nets, strict=True):
        if net is not None:
            nets[net] = (*nets.get(net, ()), f"{reference}.2")
        if reference in ambiguous_pins:
            nets[f"ALSO_{reference}"] = (f"{reference}.2",)
    peer_pin_functions = {
        f"{reference}.2": function
        for reference, function in zip(references, pin_functions, strict=True)
        if function is not None
    }
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions={
            **{f"{reference}.1": "IO" for reference in references},
            **peer_pin_functions,
        },
        pin_electrical_types={
            f"{reference}.2": electrical_type
            for reference, electrical_type in zip(references, pin_electrical_types, strict=True)
        },
        component_pin_numbers={
            reference: ("1", "2") for reference in references if reference not in missing_inventory
        },
    )


def peer_power_output_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2"),
    output_nets: tuple[str | None, ...] = ("VOUT", None),
    dnp: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
    output_electrical_types: tuple[str, ...] | None = None,
    output_function: str = "OUT",
    missing_inventory: tuple[str, ...] = (),
    ambiguous_outputs: tuple[str, ...] = (),
    part_ids: dict[str, str] | None = None,
    values: dict[str, str] | None = None,
    footprints: dict[str, str] | None = None,
) -> NetlistContract:
    return peer_component_pin_netlist(
        references=references,
        pin_nets=output_nets,
        dnp=dnp,
        symbols=symbols,
        pin_electrical_types=output_electrical_types,
        pin_function=output_function,
        missing_inventory=missing_inventory,
        ambiguous_pins=ambiguous_outputs,
        part_ids=part_ids,
        values=values,
        footprints=footprints,
    )


def peer_signal_input_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2"),
    input_nets: tuple[str | None, ...] = ("SIGNAL_A", None),
    dnp: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
    input_electrical_types: tuple[str, ...] | None = None,
    input_function: str = "IN",
    input_functions: tuple[str | None, ...] | None = None,
    missing_inventory: tuple[str, ...] = (),
    ambiguous_inputs: tuple[str, ...] = (),
) -> NetlistContract:
    return peer_component_pin_netlist(
        references=references,
        pin_nets=input_nets,
        dnp=dnp,
        symbols=symbols,
        default_symbol="Synthetic:SignalInputModule",
        pin_electrical_types=input_electrical_types or tuple("input" for _ in references),
        pin_function=input_function,
        pin_functions=input_functions,
        missing_inventory=missing_inventory,
        ambiguous_pins=ambiguous_inputs,
    )


def peer_bidirectional_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2"),
    pin_nets: tuple[str | None, ...] = ("DATA_A", None),
    dnp: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
    electrical_types: tuple[str, ...] | None = None,
    pin_function: str = "DATA_IO",
    pin_functions: tuple[str | None, ...] | None = None,
    missing_inventory: tuple[str, ...] = (),
    ambiguous_pins: tuple[str, ...] = (),
) -> NetlistContract:
    return peer_component_pin_netlist(
        references=references,
        pin_nets=pin_nets,
        dnp=dnp,
        symbols=symbols,
        default_symbol="Synthetic:BidirectionalModule",
        pin_electrical_types=electrical_types or tuple("bidirectional" for _ in references),
        pin_function=pin_function,
        pin_functions=pin_functions,
        missing_inventory=missing_inventory,
        ambiguous_pins=ambiguous_pins,
    )


def lint_report(
    observed: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    serialized = observed.model_dump_json().encode("utf-8")
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-peer-power-output",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


def component_peer_coverage(report: DesignLintReport, rule_id: str):
    return next(item for item in report.component_peer_pin_coverage if item.rule_id == rule_id)
