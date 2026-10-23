"""Small synthetic netlists for CAN TX outputs sharing one net."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def can_tx_output_netlist(
    *,
    shared: bool = True,
    references: tuple[str, ...] = ("U1", "U2"),
    tx_functions: tuple[str, ...] | None = None,
    pin_type: str = "passive",
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    """Build two synthetic CAN interfaces with either shared or split TX nets."""
    functions = tx_functions or tuple(f"CAN{index}_TX" for index, _ in enumerate(references, 1))
    components = {
        reference: ComponentContract(value="Synthetic CAN interface", footprint="")
        for reference in references
    }
    nets: dict[str, tuple[str, ...]] = {}
    pin_functions: dict[str, str] = {}
    pin_types: dict[str, str] = {}
    inventory: dict[str, tuple[str, ...]] = {}
    if shared and len(references) >= 2:
        nets["CAN_TX_SHARED"] = tuple(f"{reference}.1" for reference in references)
    for index, reference in enumerate(references):
        tx_pin = f"{reference}.1"
        rx_pin = f"{reference}.2"
        pin_functions[tx_pin] = functions[index]
        pin_functions[rx_pin] = f"CAN{index + 1}_RX"
        pin_types[tx_pin] = pin_type
        pin_types[rx_pin] = "passive"
        inventory[reference] = ("1", "2")
        if not shared:
            nets[f"CAN{index + 1}_TX"] = (tx_pin,)
        nets[f"CAN{index + 1}_RX"] = (rx_pin,)
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols={reference: "Synthetic:CanController" for reference in references},
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        component_pin_numbers=inventory,
        dnp_components=dnp_references,
    )
