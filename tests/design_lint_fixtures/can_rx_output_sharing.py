"""Synthetic CAN transceiver netlists for receiver-output sharing review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def can_rx_output_netlist(
    *,
    shared: bool = True,
    references: tuple[str, ...] = ("U1", "U2"),
    receiver_functions: tuple[str, ...] | None = None,
    receiver_type: str = "passive",
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    """Build explicit synthetic CAN transceivers with shared or separate RXD nets."""
    functions = receiver_functions or tuple("RXD" for _ in references)
    components = {
        reference: ComponentContract(value="CAN transceiver module", footprint="")
        for reference in references
    }
    component_symbols = {reference: "Synthetic:CAN_Transceiver" for reference in references}
    nets: dict[str, tuple[str, ...]] = {}
    pin_functions: dict[str, str] = {}
    pin_types: dict[str, str] = {}
    inventory: dict[str, tuple[str, ...]] = {}
    shared_receivers = tuple(f"{reference}.1" for reference in references)
    if shared and len(references) >= 2:
        nets["CAN_RX_SHARED"] = shared_receivers
    for index, reference in enumerate(references):
        rx_pin = f"{reference}.1"
        tx_pin = f"{reference}.2"
        pin_functions[rx_pin] = functions[index]
        pin_functions[tx_pin] = "TXD"
        pin_types[rx_pin] = receiver_type
        pin_types[tx_pin] = "passive"
        inventory[reference] = ("1", "2")
        if not shared:
            nets[f"CAN{index + 1}_RX"] = (rx_pin,)
        nets[f"CAN{index + 1}_TX"] = (tx_pin,)
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols=component_symbols,
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        component_pin_numbers=inventory,
        dnp_components=dnp_references,
    )
