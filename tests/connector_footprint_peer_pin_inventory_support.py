"""Typed synthetic inputs for connector peer pin-inventory regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.connector_footprint_peer_support import peer_netlist


def connector_peer_pin_inventory_netlist(
    *,
    part_ids: tuple[str | None, str | None] = ("SYNTHETIC-PART", "SYNTHETIC-PART"),
    extra_reference: str = "J2",
    extra_numbers: tuple[str, ...] = ("3",),
    anchor_assignments: tuple[str | None, str | None] = ("RETURN", "RETURN"),
    target_assignments: tuple[str | None, str | None] = ("DATA", "DATA"),
    extra_function: str = "VBUS",
    extra_electrical_type: str = "power_in",
    extra_assignment: str | None = "VBUS_NET",
    common_functions: tuple[tuple[str, str], tuple[str, str]] = (
        ("Pin_1", "Pin_1"),
        ("Pin_2", "Pin_2"),
    ),
    common_types: tuple[tuple[str, str], tuple[str, str]] = (
        ("passive", "passive"),
        ("passive", "passive"),
    ),
    missing_metadata_pin: str | None = None,
    dnp: tuple[str, ...] = (),
    same_symbol: bool = False,
) -> NetlistContract:
    """Build exact-part peers with one controlled pin-inventory difference."""
    observed = peer_netlist(
        assignments=(anchor_assignments, target_assignments),
        part_id=part_ids[0],
        dnp=dnp,
    )
    components = dict(observed.components)
    components["J1"] = components["J1"].model_copy(update={"part_id": part_ids[0]})
    components["J2"] = components["J2"].model_copy(update={"part_id": part_ids[1]})
    pin_numbers = dict(observed.component_pin_numbers)
    pin_numbers[extra_reference] = (*pin_numbers[extra_reference], *extra_numbers)
    pin_functions = {
        **observed.pin_functions,
        "J1.1": common_functions[0][0],
        "J2.1": common_functions[0][1],
        "J1.2": common_functions[1][0],
        "J2.2": common_functions[1][1],
    }
    electrical_types = {
        **observed.pin_electrical_types,
        "J1.1": common_types[0][0],
        "J2.1": common_types[0][1],
        "J1.2": common_types[1][0],
        "J2.2": common_types[1][1],
    }
    nets = dict(observed.nets)
    for number in extra_numbers:
        pin = f"{extra_reference}.{number}"
        pin_functions[pin] = extra_function
        electrical_types[pin] = extra_electrical_type
        if extra_assignment is not None:
            nets[extra_assignment] = (pin,)
    if missing_metadata_pin is not None:
        pin_functions.pop(missing_metadata_pin, None)
        electrical_types.pop(missing_metadata_pin, None)
    symbols = dict(observed.component_symbols)
    if same_symbol:
        symbols["J2"] = symbols["J1"]
    return observed.model_copy(
        update={
            "components": components,
            "component_pin_numbers": pin_numbers,
            "pin_functions": pin_functions,
            "pin_electrical_types": electrical_types,
            "nets": nets,
            "component_symbols": symbols,
        }
    )
