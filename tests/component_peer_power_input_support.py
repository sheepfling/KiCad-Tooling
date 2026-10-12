"""Synthetic fixtures for generic peer power-input assignment lint."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract

GENERIC_PEER_POWER_INPUT_RULE_ID = "component.peer_power_input_assignment_divergence"
NAMED_PEER_POWER_INPUT_OPEN_RULE_ID = "component.peer_power_input_open_assignment"
NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID = "component.peer_power_input_named_assignment_divergence"
NAMED_PEER_POWER_INPUT_ALL_OPEN_RULE_ID = "component.peer_power_input_named_all_open"


def generic_peer_power_input_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2"),
    symbols: dict[str, str] | None = None,
    part_ids: dict[str, str | None] | None = None,
    values: dict[str, str] | None = None,
    footprints: dict[str, str] | None = None,
    assignments: tuple[str | None, ...] = ("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B"),
    functions: dict[str, str | None] | None = None,
    electrical_types: dict[str, str] | None = None,
    incomplete_inventory: tuple[str, ...] = (),
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build repeated two-pin parts with generic, native power-input pin 1."""
    if len(references) != len(assignments):
        raise ValueError("Each synthetic component needs one power-input assignment")
    symbols = symbols or {reference: "Lint:GenericPowerInputPeer" for reference in references}
    part_ids = part_ids or {}
    values = values or {}
    footprints = footprints or {}
    functions = functions or {}
    electrical_types = electrical_types or {}
    nets: dict[str, tuple[str, ...]] = {"SIGNAL": tuple(f"{ref}.2" for ref in references)}
    for reference, net in zip(references, assignments, strict=True):
        if net is not None:
            nets[net] = (*nets.get(net, ()), f"{reference}.1")

    return NetlistContract(
        components={
            reference: ComponentContract(
                value=values.get(reference, "Synthetic IC"),
                footprint=footprints.get(reference, "Synthetic:Package"),
                part_id=part_ids.get(reference),
            )
            for reference in references
        },
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers={
            reference: ("1", "2")
            for reference in references
            if reference not in incomplete_inventory
        },
        pin_functions={
            pin: function
            for reference in references
            for pin, function in (
                (f"{reference}.1", functions.get(reference, "1")),
                (f"{reference}.2", "2"),
            )
            if function is not None
        },
        pin_electrical_types={
            **{
                f"{reference}.1": electrical_types.get(reference, "power_in")
                for reference in references
            },
            **{f"{reference}.2": "passive" for reference in references},
        },
    )


def named_peer_power_input_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2"),
    symbols: dict[str, str] | None = None,
    part_ids: dict[str, str | None] | None = None,
    values: dict[str, str] | None = None,
    footprints: dict[str, str] | None = None,
    assignments: tuple[str | None, ...] = ("SYNTHETIC_RAIL_A", None),
    functions: dict[str, str | None] | None = None,
    electrical_types: dict[str, str] | None = None,
    incomplete_inventory: tuple[str, ...] = (),
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build comparable peers with an explicit, non-supply power-input name."""
    return generic_peer_power_input_netlist(
        references=references,
        symbols=symbols or {reference: "Lint:NamedPeerPowerInput" for reference in references},
        part_ids=part_ids,
        values=values,
        footprints=footprints,
        assignments=assignments,
        functions=functions or {reference: "BIAS_IN" for reference in references},
        electrical_types=electrical_types,
        incomplete_inventory=incomplete_inventory,
        dnp=dnp,
    )
