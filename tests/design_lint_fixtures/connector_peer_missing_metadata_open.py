"""Minimal native-netlist fixtures for open connector peers with missing roles."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def missing_metadata_open_peer_netlist(
    *,
    target_assignments: tuple[str | None, str | None] = ("UART_RX_NET", None),
    anchor_assignments: tuple[str | None, str | None] = (
        "COMMON_REFERENCE",
        "COMMON_REFERENCE",
    ),
    missing_fields: tuple[str, ...] = ("pin_function",),
    dnp: tuple[str, ...] = (),
    incomplete_inventory: tuple[str, ...] = (),
    ambiguous_pin: str | None = None,
) -> NetlistContract:
    """Build two distinct connector symbols with one known common pin anchor."""
    components = {
        reference: ComponentContract(
            value="Synthetic peer metadata connector",
            footprint="Synthetic:Package",
        )
        for reference in ("J1", "J2")
    }
    nets: dict[str, tuple[str, ...]] = {}
    for net, pins in (
        (anchor_assignments[0], "J1.2"),
        (anchor_assignments[1], "J2.2"),
        (target_assignments[0], "J1.1"),
        (target_assignments[1], "J2.1"),
    ):
        if net is not None:
            nets[net] = (*nets.get(net, ()), pins)
    if ambiguous_pin is not None:
        nets["SYNTHETIC_AMBIGUOUS_NET"] = (
            *nets.get("SYNTHETIC_AMBIGUOUS_NET", ()),
            ambiguous_pin,
        )

    pin_functions = {
        "J1.1": "UART_RX",
        "J2.1": "~",
        "J1.2": "2",
        "J2.2": "2",
    }
    pin_electrical_types = {
        "J1.1": "input",
        "J2.1": "input",
        "J1.2": "passive",
        "J2.2": "passive",
    }
    for field in missing_fields:
        if field == "pin_function":
            pin_functions["J2.1"] = "~"
        elif field == "pin_electrical_type":
            pin_electrical_types.pop("J2.1")
        else:
            raise ValueError(f"Unsupported synthetic missing-metadata field: {field}")

    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols={
            "J1": "Lint:PeerMetadataDivergenceA",
            "J2": "Lint:PeerMetadataDivergenceB",
        },
        component_pin_numbers={
            reference: ("1", "2")
            for reference in ("J1", "J2")
            if reference not in incomplete_inventory
        },
        pin_functions=pin_functions,
        pin_electrical_types=pin_electrical_types,
    )
