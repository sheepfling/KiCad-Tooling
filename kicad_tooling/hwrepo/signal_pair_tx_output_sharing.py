"""Shared grouping predicate for same-role transmitter pins on one net."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .models import NetlistContract
from .return_nets import is_return_like_net_name

_SUPPORTED_PIN_TYPES = frozenset({"output", "tri_state", "bidirectional", "passive"})


@dataclass(frozen=True, slots=True)
class TxOutputSharingGroup:
    """One unambiguous fitted same-role TX group that is not an ERC output conflict."""

    net: str
    components: tuple[str, ...]
    pins: tuple[str, ...]
    functions: tuple[str, ...]
    channels: tuple[str, ...]
    pin_types: tuple[str, ...]


def tx_output_sharing_groups(
    observed: NetlistContract,
    *,
    role_and_channel: Callable[[str], tuple[str, str] | None],
    is_supported_reference: Callable[[str], bool],
    require_pin_inventory: bool,
    skip_return_like_nets: bool,
) -> tuple[TxOutputSharingGroup, ...]:
    """Group uniquely assigned TX pins while leaving typed output conflicts to ERC."""
    fitted = {reference.casefold(): reference for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventory = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }

    by_net: dict[str, list[tuple[str, str, str, str, str]]] = {}
    display_names: dict[str, set[str]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        canonical_reference = fitted.get(reference_key)
        if (
            not separator
            or canonical_reference is None
            or reference_key in dnp
            or not is_supported_reference(canonical_reference)
            or (
                require_pin_inventory
                and number.casefold() not in inventory.get(reference_key, set())
            )
        ):
            continue
        role_channel = role_and_channel(function)
        if role_channel is None or role_channel[0] != "tx":
            continue
        assignments = nets_by_pin.get(pin.casefold(), set())
        electrical_type = pin_types.get(pin.casefold())
        if len(assignments) != 1 or electrical_type not in _SUPPORTED_PIN_TYPES:
            continue
        net = next(iter(assignments))
        if skip_return_like_nets and is_return_like_net_name(net):
            continue
        key = net.casefold()
        by_net.setdefault(key, []).append(
            (canonical_reference, pin, function, electrical_type, role_channel[1])
        )
        display_names.setdefault(key, set()).add(net)

    groups: list[TxOutputSharingGroup] = []
    for key, endpoints in sorted(by_net.items()):
        ordered = sorted(set(endpoints), key=lambda item: tuple(part.casefold() for part in item))
        if len(display_names[key]) != 1:
            continue
        by_reference: dict[str, list[tuple[str, str, str, str, str]]] = {}
        for endpoint in ordered:
            by_reference.setdefault(endpoint[0].casefold(), []).append(endpoint)
        if len(by_reference) < 2 or any(len(items) != 1 for items in by_reference.values()):
            continue
        if sum(item[3] == "output" for item in ordered) >= 2:
            continue
        groups.append(
            TxOutputSharingGroup(
                net=next(iter(display_names[key])),
                components=tuple(
                    sorted((items[0][0] for items in by_reference.values()), key=str.casefold)
                ),
                pins=tuple(sorted((item[1] for item in ordered), key=str.casefold)),
                functions=tuple(sorted((item[2] for item in ordered), key=str.casefold)),
                channels=tuple(sorted((item[4] for item in ordered), key=str.casefold)),
                pin_types=tuple(sorted((item[3] for item in ordered), key=str.casefold)),
            )
        )
    return tuple(groups)
