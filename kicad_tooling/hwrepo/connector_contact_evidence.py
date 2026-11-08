"""Deterministic connector pin-function and net-assignment evidence."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConnectorContactEvidence:
    """One native connector contact outside a recognized interface pin group."""

    pin: str
    function: str
    nets: tuple[str, ...]


def collect_other_connector_contacts(
    connector_reference: str,
    pin_numbers: tuple[str, ...],
    pin_functions: tuple[str | None, ...],
    assigned_nets_by_pin: Mapping[str, AbstractSet[str]],
    interface_pins: Iterable[str],
) -> tuple[ConnectorContactEvidence, ...]:
    """Capture all non-interface contacts in stable pin and net order."""
    if len(pin_numbers) != len(pin_functions):
        raise ValueError("Connector contact numbers and functions must have matching lengths")
    interface_pin_keys = {pin.casefold() for pin in interface_pins}
    contacts: list[ConnectorContactEvidence] = []
    for number, function in zip(pin_numbers, pin_functions, strict=True):
        if not function or not function.strip():
            raise ValueError("Complete connector contact evidence requires native pin functions")
        pin = f"{connector_reference}.{number}"
        if pin.casefold() in interface_pin_keys:
            continue
        nets = tuple(
            sorted(
                assigned_nets_by_pin.get(pin.casefold(), ()),
                key=lambda item: (item.casefold(), item),
            )
        )
        contacts.append(ConnectorContactEvidence(pin=pin, function=function, nets=nets))
    return tuple(sorted(contacts, key=lambda item: (item.pin.casefold(), item.pin)))


def format_other_connector_contacts(
    contacts: Iterable[ConnectorContactEvidence],
) -> tuple[str, ...]:
    """Render contact evidence with explicit native assignments or open state."""
    return tuple(
        f"{item.pin} function={item.function} "
        f"nets={','.join(item.nets) if item.nets else 'unassigned'}"
        for item in contacts
    )
