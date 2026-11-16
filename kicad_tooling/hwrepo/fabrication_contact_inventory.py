"""Compare IPC-D-356 component contacts with the source PCB pad inventory."""

from __future__ import annotations

from collections import Counter

from .fabrication_artwork import Contact, UnsupportedFabricationFormat
from .fabrication_contact_source import SourceComponentPad

_ContactKey = tuple[str, str, str]
_PadKey = tuple[str, str]


def require_ipc356_source_pad_inventory(
    source_pads: tuple[SourceComponentPad, ...], contacts: tuple[Contact, ...]
) -> None:
    """Fail closed when IPC-D-356 omits, adds, or reassigns a component pad."""
    assigned: Counter[_ContactKey] = Counter()
    unassigned: Counter[_PadKey] = Counter()
    for pad in source_pads:
        key = (pad.reference.casefold(), pad.number)
        if pad.net_name is None:
            unassigned[key] += 1
        else:
            assigned[(key[0], key[1], pad.net_name)] += 1

    observed_assigned: Counter[_ContactKey] = Counter()
    observed_unassigned: Counter[_PadKey] = Counter()
    for contact in contacts:
        if contact.reference.casefold() == "via" and contact.pin.casefold() == "via":
            continue
        pad_key = (contact.reference.casefold(), contact.pin)
        if contact.net == f"N/C:{contact.reference}:{contact.pin}":
            observed_unassigned[pad_key] += 1
        else:
            observed_assigned[(pad_key[0], pad_key[1], contact.net)] += 1

    missing = assigned - observed_assigned
    unexpected = observed_assigned - assigned
    invalid_unassigned = observed_unassigned - unassigned
    if missing or unexpected or invalid_unassigned:
        details: list[str] = []
        if missing:
            details.append(
                "missing " + ", ".join(_format_key(key) for key in _sorted_keys(missing))
            )
        if unexpected:
            details.append(
                "unexpected " + ", ".join(_format_key(key) for key in _sorted_keys(unexpected))
            )
        if invalid_unassigned:
            details.append(
                "unexpected unassigned "
                + ", ".join(
                    f"{reference}.{pad}"
                    for reference, pad in sorted(
                        invalid_unassigned, key=lambda key: (key[0], key[1])
                    )
                )
            )
        raise UnsupportedFabricationFormat(
            "IPC-D-356 component contact inventory differs from source PCB pads: "
            + "; ".join(details)
        )


def _format_key(key: _ContactKey) -> str:
    reference, pad, net = key
    return f"{reference}.{pad}={net}"


def _sorted_keys(counter: Counter[_ContactKey]) -> tuple[_ContactKey, ...]:
    return tuple(sorted(counter, key=lambda key: (key[0], key[1], key[2])))
