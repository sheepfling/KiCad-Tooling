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
    _match_ipc356_source_pad_centers(source_pads, contacts)


def require_ipc356_source_pad_dimensions(
    source_pads: tuple[SourceComponentPad, ...], contacts: tuple[Contact, ...]
) -> None:
    """Fail closed when IPC-D-356 pad sizes differ at a matched source center."""
    pairs = _match_ipc356_source_pad_centers(source_pads, contacts)
    mismatches: list[str] = []
    for source, contact in pairs:
        if (
            source.size_x_nm is None
            or source.size_y_nm is None
            or contact.size_x_mm is None
            or contact.size_y_mm is None
        ):
            raise UnsupportedFabricationFormat(
                f"IPC-D-356 pad dimensions are unavailable for {source.reference}.{source.number}"
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
                f"{source.reference}.{source.number} at ({source.x_nm}, {-source.y_nm}) nm "
                f"exports size ({observed_x_nm}, {observed_y_nm}) nm; expected "
                f"({expected_x_nm}, {expected_y_nm}) nm"
            )
    if mismatches:
        raise UnsupportedFabricationFormat(
            "IPC-D-356 pad dimensions differ from source PCB pad geometry: "
            + "; ".join(sorted(mismatches))
        )


def _match_ipc356_source_pad_centers(
    source_pads: tuple[SourceComponentPad, ...], contacts: tuple[Contact, ...]
) -> tuple[tuple[SourceComponentPad, Contact], ...]:
    """Pair component contacts one-to-one by identity and quantized board center."""
    source_by_pad: dict[_PadKey, list[SourceComponentPad]] = defaultdict(list)
    contacts_by_pad: dict[_PadKey, list[Contact]] = defaultdict(list)
    for pad in source_pads:
        source_by_pad[(pad.reference.casefold(), pad.number)].append(pad)
    for contact in contacts:
        if contact.reference.casefold() == "via" and contact.pin.casefold() == "via":
            continue
        contacts_by_pad[(contact.reference.casefold(), contact.pin)].append(contact)

    pairs: list[tuple[SourceComponentPad, Contact]] = []
    for key in sorted(contacts_by_pad):
        source_centers = sorted(
            source_by_pad.get(key, ()),
            key=lambda pad: (
                pad.x_nm,
                pad.y_nm,
                pad.net_name or "",
                pad.pad_shape or "",
                pad.size_x_nm if pad.size_x_nm is not None else -1,
                pad.size_y_nm if pad.size_y_nm is not None else -1,
            ),
        )
        observed = sorted(
            contacts_by_pad[key],
            key=lambda contact: (
                contact.x_mm,
                contact.y_mm,
                contact.net,
                contact.size_x_mm if contact.size_x_mm is not None else -1.0,
                contact.size_y_mm if contact.size_y_mm is not None else -1.0,
            ),
        )
        if len(source_centers) != len(observed):
            raise UnsupportedFabricationFormat(
                f"IPC-D-356 coordinate inventory has no unique source match for {key[0]}.{key[1]}"
            )
        unused = list(source_centers)
        for contact in observed:
            observed_x_nm = round(contact.x_mm * _NM_PER_MM)
            observed_y_nm = round(contact.y_mm * _NM_PER_MM)
            tolerance_nm = contact.coordinate_resolution_nm // 2 + 1
            matches = [
                pad
                for pad in unused
                if abs(observed_x_nm - pad.x_nm) <= tolerance_nm
                and abs(observed_y_nm + pad.y_nm) <= tolerance_nm
            ]
            if not matches:
                raise UnsupportedFabricationFormat(
                    "IPC-D-356 component contact coordinates differ from source PCB pad centers: "
                    f"{key[0]}.{key[1]} exported at "
                    f"({observed_x_nm:.0f}, {observed_y_nm:.0f}) nm has no source center"
                )
            if len(matches) > 1:
                size_matches = [pad for pad in matches if _source_pad_size_matches(pad, contact)]
                if len(size_matches) == 1:
                    source = size_matches[0]
                elif all(
                    _source_pad_signature(pad) == _source_pad_signature(matches[0])
                    for pad in matches
                ):
                    source = matches[0]
                else:
                    raise UnsupportedFabricationFormat(
                        f"IPC-D-356 contact has an ambiguous source center for {key[0]}.{key[1]}"
                    )
            else:
                source = matches[0]
            unused.remove(source)
            pairs.append((source, contact))
    return tuple(pairs)


def _source_pad_size_matches(source: SourceComponentPad, contact: Contact) -> bool:
    if (
        source.size_x_nm is None
        or source.size_y_nm is None
        or contact.size_x_mm is None
        or contact.size_y_mm is None
    ):
        return False
    expected_y_nm = 0 if source.pad_shape == "circle" else source.size_y_nm
    tolerance_nm = contact.coordinate_resolution_nm // 2 + 1
    return (
        abs(round(contact.size_x_mm * _NM_PER_MM) - source.size_x_nm) <= tolerance_nm
        and abs(round(contact.size_y_mm * _NM_PER_MM) - expected_y_nm) <= tolerance_nm
    )


def _source_pad_signature(source: SourceComponentPad) -> tuple[object, ...]:
    return (
        source.x_nm,
        source.y_nm,
        source.net_name,
        source.contact_layer,
        source.pad_shape,
        source.size_x_nm,
        source.size_y_nm,
    )
