"""Synthetic netlists for CAN peers sharing line nets and reference domains."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def can_peer_reference_netlist(
    *,
    reference_nets: dict[str, str] | None = None,
    line_nets: dict[str, tuple[str, str]] | None = None,
    symbols: dict[str, str] | None = None,
    dnp: tuple[str, ...] = (),
    incomplete_reference_types: tuple[str, ...] = (),
    reference_functions: dict[str, str] | None = None,
) -> NetlistContract:
    """Build fitted CAN line-pair peers with complete explicit pin inventories."""
    reference_nets = reference_nets or {"U1": "GND_A", "U2": "GND_B"}
    references = tuple(sorted(reference_nets))
    line_nets = line_nets or {reference: ("CAN_HIGH", "CAN_LOW") for reference in references}
    symbols = symbols or {
        reference: f"Synthetic:CANEndpoint{index}"
        for index, reference in enumerate(references, start=1)
    }
    reference_functions = reference_functions or {}
    components = {
        reference: ComponentContract(value="Synthetic CAN endpoint", footprint="Synthetic:SOIC")
        for reference in references
    }
    nets: dict[str, list[str]] = {}
    pin_functions: dict[str, str] = {}
    pin_electrical_types: dict[str, str] = {}
    for reference in references:
        canh_pin, canl_pin = f"{reference}.1", f"{reference}.2"
        reference_pin, supply_pin = f"{reference}.3", f"{reference}.4"
        pin_functions[canh_pin] = "CANH"
        pin_functions[canl_pin] = "CAN_L"
        pin_functions[reference_pin] = reference_functions.get(reference, "GND")
        pin_functions[supply_pin] = "VDD"
        pin_electrical_types.update(
            {
                canh_pin: "passive",
                canl_pin: "passive",
                reference_pin: "passive",
                supply_pin: "passive",
            }
        )
        canh_net, canl_net = line_nets[reference]
        nets.setdefault(canh_net, []).append(canh_pin)
        nets.setdefault(canl_net, []).append(canl_pin)
        nets.setdefault(reference_nets[reference], []).append(reference_pin)
        nets.setdefault("VIO_3V3", []).append(supply_pin)
    for reference in incomplete_reference_types:
        pin_electrical_types.pop(f"{reference}.3", None)
    return NetlistContract(
        components=components,
        component_symbols=symbols,
        component_pin_numbers={reference: ("1", "2", "3", "4") for reference in references},
        pin_functions=pin_functions,
        pin_electrical_types=pin_electrical_types,
        nets={net: tuple(pins) for net, pins in nets.items()},
        dnp_components=dnp,
    )
