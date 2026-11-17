"""Bind IPC-D-356 access layers to source PCB component-pad layers."""

from __future__ import annotations

from collections import Counter, defaultdict

from .fabrication_artwork import Contact, UnsupportedFabricationFormat
from .fabrication_contact_source import SourceComponentPad

_PadKey = tuple[str, str]


def require_ipc356_source_pad_layers(
    source_pads: tuple[SourceComponentPad, ...], contacts: tuple[Contact, ...]
) -> None:
    """Require each IPC-D-356 component access class to match source pad copper."""
    source_by_pad: dict[_PadKey, list[SourceComponentPad]] = defaultdict(list)
    contacts_by_pad: dict[_PadKey, list[Contact]] = defaultdict(list)
    for pad in source_pads:
        source_by_pad[(pad.reference.casefold(), pad.number)].append(pad)
    for contact in contacts:
        if contact.reference.casefold() == "via" and contact.pin.casefold() == "via":
            continue
        contacts_by_pad[(contact.reference.casefold(), contact.pin)].append(contact)

    for key in sorted(contacts_by_pad):
        source = source_by_pad.get(key, ())
        observed = contacts_by_pad[key]
        if len(source) != len(observed):
            raise UnsupportedFabricationFormat(
                f"IPC-D-356 layer inventory has no unique source match for {key[0]}.{key[1]}"
            )
        if any(pad.contact_layer is None for pad in source):
            raise UnsupportedFabricationFormat(
                f"source PCB pad {key[0]}.{key[1]} has unsupported or ambiguous copper-layer classification"
            )
        expected_layers = Counter(
            pad.contact_layer for pad in source if pad.contact_layer is not None
        )
        observed_layers = Counter(contact.layer for contact in observed)
        if expected_layers != observed_layers:
            expected = ", ".join(
                f"{layer} x{count}" for layer, count in sorted(expected_layers.items())
            )
            actual = ", ".join(
                f"{layer} x{count}" for layer, count in sorted(observed_layers.items())
            )
            raise UnsupportedFabricationFormat(
                f"IPC-D-356 layer classification differs from source PCB pad "
                f"{key[0]}.{key[1]} (expected {expected}; observed {actual})"
            )
