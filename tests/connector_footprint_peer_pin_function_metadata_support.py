"""Synthetic exact-part connector peers for function-metadata review tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.connector_footprint_peer_support import peer_netlist


def metadata_peer_netlist(
    *,
    generic_peer: str = "J1",
    anchor_functions: tuple[str, str] = ("GND", "GND"),
    named_functions: tuple[str, str] = ("UART_TX", "UART_TX"),
    assignments: tuple[tuple[str | None, str | None], ...] = (
        ("RETURN", "RETURN"),
        ("DATA", "DATA"),
    ),
    target_types: tuple[str, str] = ("passive", "passive"),
    anchor_types: tuple[str, str] = ("passive", "passive"),
    part_ids: tuple[str | None, str | None] = ("SYNTHETIC-PART", "SYNTHETIC-PART"),
    dnp: tuple[str, ...] = (),
    incomplete_inventory: bool = False,
    missing_metadata_pin: str | None = None,
    same_symbol: bool = False,
) -> NetlistContract:
    """Create exact-part peers with one controllable generic function label."""
    observed = peer_netlist(
        assignments=assignments,
        functions=(anchor_functions[0], named_functions[0]),
        electrical_types=(anchor_types[0], target_types[0]),
        part_id=part_ids[0],
        dnp=dnp,
        incomplete_inventory=incomplete_inventory,
        missing_metadata_pin=missing_metadata_pin,
    )
    functions = dict(observed.pin_functions)
    electrical_types = dict(observed.pin_electrical_types)
    functions.update({"J2.1": anchor_functions[1], "J2.2": named_functions[1]})
    electrical_types.update({"J2.1": anchor_types[1], "J2.2": target_types[1]})
    if generic_peer in {"J1", "J2"}:
        functions[f"{generic_peer}.2"] = "Pin_2"
    if missing_metadata_pin is not None:
        functions.pop(missing_metadata_pin, None)
        electrical_types.pop(missing_metadata_pin, None)
    components = dict(observed.components)
    components["J1"] = components["J1"].model_copy(update={"part_id": part_ids[0]})
    components["J2"] = components["J2"].model_copy(update={"part_id": part_ids[1]})
    symbols = dict(observed.component_symbols)
    if same_symbol:
        symbols["J2"] = symbols["J1"]
    return observed.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "pin_functions": functions,
            "pin_electrical_types": electrical_types,
        }
    )
