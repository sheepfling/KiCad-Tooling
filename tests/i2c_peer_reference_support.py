"""Small native-netlist builders for synthetic I2C reference-review tests."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def i2c_peer_netlist(
    *,
    reference_nets: Mapping[str, str] | None = None,
    signal_nets: Mapping[str, tuple[str, str]] | None = None,
    symbols: Mapping[str, str] | None = None,
    part_ids: Mapping[str, str] | None = None,
    dnp: tuple[str, ...] = (),
    incomplete_reference_types: tuple[str, ...] = (),
    shield_nets: Mapping[str, str] | None = None,
) -> NetlistContract:
    """Build exact I2C peer pin inventories without a product-specific design."""
    if reference_nets is None:
        reference_nets = {"U1": "GND_A", "U2": "GND_B"}
    references = tuple(sorted(reference_nets))
    signal_nets = signal_nets or {reference: ("I2C_SDA", "I2C_SCL") for reference in references}
    symbols = symbols or {
        reference: f"Synthetic:I2cPeer{index}"
        for index, reference in enumerate(references, start=1)
    }
    part_ids = part_ids or {}
    shield_nets = shield_nets or {}

    components = {
        reference: ComponentContract(
            value="Synthetic I2C peer",
            footprint="Synthetic:SOIC",
            part_id=part_ids.get(reference),
        )
        for reference in references
    }
    component_symbols = symbols
    component_pin_numbers = {reference: ("1", "2", "3", "4") for reference in references}
    pin_functions: dict[str, str] = {}
    pin_electrical_types: dict[str, str] = {}
    nets: dict[str, list[str]] = {}
    for reference in references:
        sda_net, scl_net = signal_nets[reference]
        pin_functions.update(
            {
                f"{reference}.1": "SDA",
                f"{reference}.2": "I2C_SCL",
                f"{reference}.3": "GND",
                f"{reference}.4": "SHIELD",
            }
        )
        pin_electrical_types.update(
            {
                f"{reference}.1": "bidirectional",
                f"{reference}.2": "input",
                f"{reference}.3": "power_in",
                f"{reference}.4": "passive",
            }
        )
        nets.setdefault(sda_net, []).append(f"{reference}.1")
        nets.setdefault(scl_net, []).append(f"{reference}.2")
        nets.setdefault(reference_nets[reference], []).append(f"{reference}.3")
        if reference in shield_nets:
            nets.setdefault(shield_nets[reference], []).append(f"{reference}.4")
    for reference in incomplete_reference_types:
        pin_electrical_types.pop(f"{reference}.3", None)

    return NetlistContract(
        components=components,
        component_symbols=component_symbols,
        component_pin_numbers=component_pin_numbers,
        pin_functions=pin_functions,
        pin_electrical_types=pin_electrical_types,
        nets={net: tuple(pins) for net, pins in nets.items()},
        dnp_components=dnp,
    )
