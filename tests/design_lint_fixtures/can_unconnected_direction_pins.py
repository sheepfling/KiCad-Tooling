"""Synthetic CAN/FDCAN direction-function netlists for open-pin review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def can_unconnected_direction_netlist(
    *,
    open_pins: tuple[str, ...] = ("U1.2",),
    dnp_components: tuple[str, ...] = (),
    functions: dict[str, str] | None = None,
    pin_numbers: tuple[str, ...] = ("1", "2"),
) -> NetlistContract:
    """Create a native-shaped fitted transceiver with one partially open pair."""
    pin_functions = functions or {"U1.1": "CAN1_TX", "U1.2": "CAN1_RX"}
    assignments = {"CAN1_TX_NET": ("U1.1",), "CAN1_RX_NET": ("U1.2",)}
    open_keys = {pin.casefold() for pin in open_pins}
    nets = {
        net: tuple(pin for pin in pins if pin.casefold() not in open_keys)
        for net, pins in assignments.items()
    }
    nets = {net: pins for net, pins in nets.items() if pins}
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic CAN controller", footprint="Synthetic:QFN")
        },
        nets=nets,
        unconnected_nets={"unconnected": tuple(sorted(open_pins))},
        dnp_components=dnp_components,
        component_symbols={"U1": "Synthetic:CanController"},
        pin_functions=pin_functions,
        component_pin_numbers={"U1": pin_numbers},
    )
