"""Typed synthetic netlists for all-open generic component peer pins."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def generic_component_peer_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2"),
    anchor_nets: tuple[str | None, ...] = ("SHARED", "SHARED"),
    target_nets: tuple[str | None, ...] = (None, None),
    symbols: dict[str, str] | None = None,
    target_types: tuple[str, ...] = ("passive", "passive"),
    pin_functions: tuple[str | None, str | None] = ("ANCHOR", "Pin_2"),
    dnp: tuple[str, ...] = (),
    part_ids: dict[str, str] | None = None,
    values: dict[str, str] | None = None,
    footprints: dict[str, str] | None = None,
) -> NetlistContract:
    """Build peers with a stable anchor and a configurable generic second pin."""
    if not (len(references) == len(anchor_nets) == len(target_nets) == len(target_types)):
        raise ValueError("Each peer needs matching anchor, target, and electrical-type cases")
    symbols = symbols or {reference: "Synthetic:PeerModule" for reference in references}
    part_ids = part_ids or {}
    values = values or {}
    footprints = footprints or {}
    components = {
        reference: ComponentContract(
            value=values.get(reference, "Synthetic peer module"),
            footprint=footprints.get(reference, "Synthetic:Module"),
            part_id=part_ids.get(reference),
        )
        for reference in references
    }
    nets: dict[str, list[str]] = {}
    for reference, anchor_net, target_net in zip(references, anchor_nets, target_nets, strict=True):
        if anchor_net is not None:
            nets.setdefault(anchor_net, []).append(f"{reference}.1")
        if target_net is not None:
            nets.setdefault(target_net, []).append(f"{reference}.2")
    functions = {
        f"{reference}.{number}": function
        for reference in references
        for number, function in zip(("1", "2"), pin_functions, strict=True)
        if function is not None
    }
    return NetlistContract(
        components=components,
        nets={net: tuple(pins) for net, pins in nets.items()},
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=functions,
        pin_electrical_types={
            **{f"{reference}.1": "passive" for reference in references},
            **{
                f"{reference}.2": electrical_type
                for reference, electrical_type in zip(references, target_types, strict=True)
            },
        },
        component_pin_numbers={reference: ("1", "2") for reference in references},
    )


def generic_component_peer_mixed_netlist(
    *,
    anchor_nets: tuple[str | None, ...] = ("SHARED", "SHARED", "SHARED"),
    target_nets: tuple[str | None, ...] = ("LOAD", "LOAD", None),
    target_types: tuple[str, ...] = ("passive", "passive", "passive"),
    symbols: dict[str, str] | None = None,
    pin_functions: tuple[str | None, str | None] = ("ANCHOR", "Pin_2"),
    dnp: tuple[str, ...] = (),
    part_ids: dict[str, str] | None = None,
    values: dict[str, str] | None = None,
    footprints: dict[str, str] | None = None,
) -> NetlistContract:
    """Build three peers with two agreeing target nets and one open target."""
    references = ("U1", "U2", "U3")
    return generic_component_peer_netlist(
        references=references,
        anchor_nets=anchor_nets,
        target_nets=target_nets,
        target_types=target_types,
        symbols=symbols,
        pin_functions=pin_functions,
        dnp=dnp,
        part_ids=part_ids,
        values=values,
        footprints=footprints,
    )
