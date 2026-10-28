"""Normalize the raw model input shape accepted by ``NetlistContract``."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TypeAlias, cast

from pydantic import BaseModel, ValidationInfo

from .netlist_pins import is_native_unconnected_net_name

NetlistInputValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | BaseModel
    | list["NetlistInputValue"]
    | tuple["NetlistInputValue", ...]
    | Mapping[str, "NetlistInputValue"]
)
NetlistInputKey: TypeAlias = str | int | float | bool | bytes | None | tuple[str, ...]
NetlistRawObject: TypeAlias = Mapping[NetlistInputKey, NetlistInputValue]
NetlistInputObject: TypeAlias = Mapping[str, NetlistInputValue]
NetlistRawValue: TypeAlias = NetlistInputValue | NetlistRawObject


def _has_string_keys(value: NetlistRawObject) -> bool:
    keys: Iterable[NetlistInputKey] = cast(Iterable[NetlistInputKey], value)
    for key in keys:
        if not isinstance(key, str):
            return False
    return True


def normalize_native_unconnected_nets(value: NetlistRawValue, info: ValidationInfo) -> object:
    """Move KiCad's per-pin unconnected sentinels out of electrical nets."""
    if not isinstance(value, Mapping):
        return value
    raw_source: NetlistRawObject = cast(NetlistRawObject, value)
    if not _has_string_keys(raw_source):
        return cast(object, value)
    source: NetlistInputObject = cast(NetlistInputObject, raw_source)
    nets: NetlistInputValue = source.get("nets", None)
    empty_object: NetlistInputValue = {}
    existing_unconnected: NetlistInputValue = source.get("unconnected_nets", empty_object)
    if not isinstance(nets, Mapping) or not isinstance(existing_unconnected, Mapping):
        return cast(object, value)
    raw_nets: NetlistRawObject = cast(NetlistRawObject, nets)
    raw_unconnected: NetlistRawObject = cast(NetlistRawObject, existing_unconnected)
    if not _has_string_keys(raw_nets) or not _has_string_keys(raw_unconnected):
        return cast(object, value)
    net_mapping: NetlistInputObject = cast(NetlistInputObject, raw_nets)
    unconnected_mapping: NetlistInputObject = cast(NetlistInputObject, raw_unconnected)

    assigned: dict[str, NetlistInputValue] = {}
    unconnected: dict[str, NetlistInputValue] = dict(unconnected_mapping)
    moved = False
    for name, pins in net_mapping.items():
        if not is_native_unconnected_net_name(name):
            assigned[name] = pins
            continue
        moved = True
        previous: NetlistInputValue | None = unconnected.get(name)
        if isinstance(previous, (tuple, list)) and isinstance(pins, (tuple, list)):
            previous_items: tuple[NetlistInputValue, ...] | list[NetlistInputValue] = cast(
                tuple[NetlistInputValue, ...] | list[NetlistInputValue], previous
            )
            current_items: tuple[NetlistInputValue, ...] | list[NetlistInputValue] = cast(
                tuple[NetlistInputValue, ...] | list[NetlistInputValue], pins
            )
            if all(isinstance(pin, str) for pin in previous_items) and all(
                isinstance(pin, str) for pin in current_items
            ):
                previous_pins: tuple[str, ...] | list[str] = cast(
                    tuple[str, ...] | list[str], previous_items
                )
                current_pins: tuple[str, ...] | list[str] = cast(
                    tuple[str, ...] | list[str], current_items
                )
                unconnected[name] = tuple(
                    sorted(set(previous_pins) | set(current_pins), key=str.casefold)
                )
            else:
                unconnected[name] = pins
        else:
            unconnected[name] = pins

    if not moved and info.mode != "json":
        return cast(object, value)
    normalized: dict[str, NetlistInputValue] = dict(source.items())
    if moved:
        normalized["nets"] = assigned
        normalized["unconnected_nets"] = unconnected
    if info.mode == "json":
        # Returning a Python mapping switches later validation to Python mode.
        # Convert JSON arrays for tuple fields before strict field validation.
        for field in ("nets", "unconnected_nets", "component_pin_numbers"):
            table: NetlistInputValue | None = normalized.get(field)
            if isinstance(table, Mapping):
                table_mapping: NetlistInputObject = cast(NetlistInputObject, table)
                converted: dict[str, NetlistInputValue] = {}
                for key, items in table_mapping.items():
                    row: NetlistInputValue = items
                    converted[key] = (
                        tuple(cast(list[NetlistInputValue], row)) if isinstance(row, list) else row
                    )
                normalized[field] = converted
        dnp_components: NetlistInputValue | None = normalized.get("dnp_components")
        if isinstance(dnp_components, list):
            normalized["dnp_components"] = tuple(cast(list[NetlistInputValue], dnp_components))
    return normalized
