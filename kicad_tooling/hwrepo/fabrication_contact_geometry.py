"""Match IPC-D-356 contact centers to transformed PCB source-pad centers."""

from __future__ import annotations

from collections import defaultdict

from .fabrication_artwork import Contact, UnsupportedFabricationFormat
from .fabrication_contact_source import SourceComponentPad

_NM_PER_MM = 1_000_000
_PadKey = tuple[str, str]


def require_ipc356_source_pad_coordinates(
    source_pads: tuple[SourceComponentPad, ...], contacts: tuple[Contact, ...]
) -> None:
    """Fail closed when an IPC-D-356 component record is not at its source pad."""
    source_by_pad: dict[_PadKey, list[SourceComponentPad]] = defaultdict(list)
    contacts_by_pad: dict[_PadKey, list[Contact]] = defaultdict(list)
    for pad in source_pads:
        source_by_pad[(pad.reference.casefold(), pad.number)].append(pad)
    for contact in contacts:
        if contact.reference.casefold() == "via" and contact.pin.casefold() == "via":
            continue
        contacts_by_pad[(contact.reference.casefold(), contact.pin)].append(contact)

    mismatches: list[str] = []
    for key in sorted(contacts_by_pad):
        source_centers = sorted(
            source_by_pad.get(key, ()), key=lambda pad: (pad.x_nm, pad.y_nm, pad.net_name or "")
        )
        observed = sorted(
            contacts_by_pad[key], key=lambda contact: (contact.x_mm, contact.y_mm, contact.net)
        )
        if len(source_centers) != len(observed):
            raise UnsupportedFabricationFormat(
                f"IPC-D-356 coordinate inventory has no unique source match for {key[0]}.{key[1]}"
            )
        for source, contact in zip(source_centers, observed, strict=True):
            observed_x_nm = contact.x_mm * _NM_PER_MM
            observed_y_nm = contact.y_mm * _NM_PER_MM
            expected_x_nm = source.x_nm
            expected_y_nm = -source.y_nm
            tolerance_nm = contact.coordinate_resolution_nm // 2 + 1
            if (
                abs(observed_x_nm - expected_x_nm) > tolerance_nm
                or abs(observed_y_nm - expected_y_nm) > tolerance_nm
            ):
                mismatches.append(
                    f"{source.reference}.{source.number} exported at "
                    f"({observed_x_nm:.0f}, {observed_y_nm:.0f}) nm; expected "
                    f"({expected_x_nm}, {-expected_y_nm}) nm"
                )
    if mismatches:
        raise UnsupportedFabricationFormat(
            "IPC-D-356 component contact coordinates differ from source PCB pad centers: "
            + "; ".join(sorted(mismatches))
        )


def require_ipc356_source_pad_dimensions(
    source_pads: tuple[SourceComponentPad, ...], contacts: tuple[Contact, ...]
) -> None:
    """Fail closed when IPC-D-356 pad sizes differ from source pad dimensions."""
    source_by_pad: dict[_PadKey, list[SourceComponentPad]] = defaultdict(list)
    contacts_by_pad: dict[_PadKey, list[Contact]] = defaultdict(list)
    for pad in source_pads:
        source_by_pad[(pad.reference.casefold(), pad.number)].append(pad)
    for contact in contacts:
        if contact.reference.casefold() == "via" and contact.pin.casefold() == "via":
            continue
        contacts_by_pad[(contact.reference.casefold(), contact.pin)].append(contact)

    mismatches: list[str] = []
    for key in sorted(contacts_by_pad):
        source_dimensions = sorted(
            source_by_pad.get(key, ()),
            key=lambda pad: (
                pad.size_x_nm if pad.size_x_nm is not None else -1,
                0 if pad.pad_shape == "circle" else pad.size_y_nm or -1,
                pad.x_nm,
                pad.y_nm,
            ),
        )
        observed = sorted(
            contacts_by_pad[key],
            key=lambda contact: (
                contact.size_x_mm if contact.size_x_mm is not None else -1.0,
                contact.size_y_mm if contact.size_y_mm is not None else -1.0,
                contact.x_mm,
                contact.y_mm,
            ),
        )
        if len(source_dimensions) != len(observed):
            raise UnsupportedFabricationFormat(
                f"IPC-D-356 size inventory has no unique source match for {key[0]}.{key[1]}"
            )
        for source, contact in zip(source_dimensions, observed, strict=True):
            if (
                source.size_x_nm is None
                or source.size_y_nm is None
                or contact.size_x_mm is None
                or contact.size_y_mm is None
            ):
                raise UnsupportedFabricationFormat(
                    f"IPC-D-356 pad dimensions are unavailable for {key[0]}.{key[1]}"
                )
            expected_x_nm = source.size_x_nm
            expected_y_nm = 0 if source.pad_shape == "circle" else source.size_y_nm
            observed_x_nm = round(contact.size_x_mm * _NM_PER_MM)
            observed_y_nm = round(contact.size_y_mm * _NM_PER_MM)
            tolerance_nm = contact.coordinate_resolution_nm // 2 + 1
            if (
                abs(observed_x_nm - expected_x_nm) > tolerance_nm
                or abs(observed_y_nm - expected_y_nm) > tolerance_nm
            ):
                mismatches.append(
                    f"{source.reference}.{source.number} exports size "
                    f"({observed_x_nm}, {observed_y_nm}) nm; expected "
                    f"({expected_x_nm}, {expected_y_nm}) nm"
                )
    if mismatches:
        raise UnsupportedFabricationFormat(
            "IPC-D-356 pad dimensions differ from source PCB pad geometry: "
            + "; ".join(sorted(mismatches))
        )
