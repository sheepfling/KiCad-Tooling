"""Bind IPC-D-356 VIA contacts to full-stack vias in the source PCB."""

from __future__ import annotations

from dataclasses import dataclass

from .fabrication_artwork import Contact, UnsupportedFabricationFormat
from .fabrication_contact_source import millimeters_to_nanometers
from .kicad_sexpr import sexpr_atoms, sexpr_field, sexpr_nodes, sexpr_root
from .pcb_board_net_inventory import pcb_board_net_map

_NM_PER_MM = 1_000_000


@dataclass(frozen=True, slots=True)
class SourceVia:
    """A source PCB via's named net, center, drill, and circular copper size."""

    net_name: str
    x_nm: int
    y_nm: int
    drill_nm: int
    copper_diameter_nm: int | None = None


def source_board_vias(board_text: str) -> tuple[SourceVia, ...]:
    """Read source vias after mapping each numeric net code to its board name."""
    try:
        root = sexpr_root(board_text, "kicad_pcb")
        net_map = pcb_board_net_map(board_text)
        if net_map is None:
            raise UnsupportedFabricationFormat("source board has an incomplete named-net inventory")
        names_by_code = dict(net_map)
        result: list[SourceVia] = []
        for via in sexpr_nodes(board_text, root, "via"):
            if sexpr_nodes(board_text, via, "padstack"):
                raise UnsupportedFabricationFormat(
                    "source via has a custom padstack with unsupported layer-specific sizes"
                )
            position = sexpr_field(board_text, via, "at")
            if len(position) != 2:
                raise UnsupportedFabricationFormat("source via has an unsupported position")
            size = sexpr_field(board_text, via, "size", required=False)
            if len(size) != 1:
                raise UnsupportedFabricationFormat("source via has an unsupported copper size")
            copper_diameter_nm = round(millimeters_to_nanometers(size[0]))
            if copper_diameter_nm <= 0:
                raise UnsupportedFabricationFormat("source via has a non-positive copper size")
            drill = sexpr_field(board_text, via, "drill")
            if len(drill) != 1:
                raise UnsupportedFabricationFormat("source via has an unsupported drill size")
            drill_nm = round(millimeters_to_nanometers(drill[0]))
            if drill_nm <= 0:
                raise UnsupportedFabricationFormat("source via has a non-positive drill size")
            net_nodes = sexpr_nodes(board_text, via, "net")
            if len(net_nodes) != 1:
                raise UnsupportedFabricationFormat("source via has no unique net assignment")
            net_atoms = sexpr_atoms(board_text, net_nodes[0])
            if len(net_atoms) != 2:
                raise UnsupportedFabricationFormat("source via has a malformed net assignment")
            try:
                net_code = int(net_atoms[1])
            except ValueError as exc:
                raise UnsupportedFabricationFormat("source via has a malformed net code") from exc
            net_name = names_by_code.get(net_code)
            if net_code <= 0 or not net_name:
                raise UnsupportedFabricationFormat(
                    "source via has an unnamed or unknown net assignment"
                )
            result.append(
                SourceVia(
                    net_name,
                    round(millimeters_to_nanometers(position[0])),
                    round(millimeters_to_nanometers(position[1])),
                    drill_nm,
                    copper_diameter_nm,
                )
            )
        return tuple(sorted(result, key=lambda item: (item.net_name, item.x_nm, item.y_nm)))
    except UnsupportedFabricationFormat:
        raise
    except (OverflowError, ValueError) as exc:
        raise UnsupportedFabricationFormat("source via inventory is malformed") from exc


def require_ipc356_source_via_inventory(
    source_vias: tuple[SourceVia, ...], contacts: tuple[Contact, ...]
) -> None:
    """Require a one-to-one net-and-center match for each source and exported via."""
    _matched_ipc356_source_vias(source_vias, contacts)


def require_ipc356_source_via_geometry(
    source_vias: tuple[SourceVia, ...], contacts: tuple[Contact, ...]
) -> None:
    """Require matching source via identity, center, and circular copper size."""
    _require_ipc356_source_via_dimensions(_matched_ipc356_source_vias(source_vias, contacts))


def require_ipc356_source_via_access_codes(
    source_vias: tuple[SourceVia, ...], contacts: tuple[Contact, ...]
) -> None:
    """Require supported full-stack via records to use the through-access code."""
    for via, contact in _matched_ipc356_source_vias(source_vias, contacts):
        if contact.access_code is None:
            raise UnsupportedFabricationFormat(
                f"IPC-D-356 access code is unavailable for VIA on {via.net_name}"
            )
        if contact.access_code != 0:
            raise UnsupportedFabricationFormat(
                "IPC-D-356 access code differs from full-stack source PCB via "
                f"on {via.net_name} at ({via.x_nm}, {-via.y_nm}) nm "
                f"(expected A00; observed A{contact.access_code:02d})"
            )


def _matched_ipc356_source_vias(
    source_vias: tuple[SourceVia, ...], contacts: tuple[Contact, ...]
) -> tuple[tuple[SourceVia, Contact], ...]:
    """Return unique source-to-artifact VIA matches using net and quantized center."""
    via_contacts = tuple(
        sorted(
            (_via_contact(item) for item in contacts if _is_via(item)),
            key=_contact_key,
        )
    )
    source = tuple(sorted(source_vias, key=lambda item: (item.net_name, item.x_nm, item.y_nm)))
    if len(via_contacts) != len(source):
        raise UnsupportedFabricationFormat(
            "IPC-D-356 VIA contact count differs from source PCB vias "
            f"(artifact {len(via_contacts)}, source {len(source)})"
        )

    matched: set[int] = set()
    pairs: list[tuple[SourceVia, Contact]] = []
    for contact in via_contacts:
        observed_x_nm = round(contact.x_mm * _NM_PER_MM)
        observed_y_nm = round(contact.y_mm * _NM_PER_MM)
        tolerance_nm = contact.coordinate_resolution_nm // 2 + 1
        matches = [
            index
            for index, via in enumerate(source)
            if via.net_name == contact.net
            and abs(observed_x_nm - via.x_nm) <= tolerance_nm
            and abs(observed_y_nm + via.y_nm) <= tolerance_nm
        ]
        if len(matches) != 1:
            if len(matches) > 1:
                raise UnsupportedFabricationFormat(
                    f"IPC-D-356 VIA contact on {contact.net} has an ambiguous source match"
                )
            raise UnsupportedFabricationFormat(
                f"IPC-D-356 VIA contact on {contact.net} at "
                f"({observed_x_nm:.0f}, {observed_y_nm:.0f}) nm has no matching source via"
            )
        if matches[0] in matched:
            raise UnsupportedFabricationFormat(
                f"multiple IPC-D-356 VIA contacts match source via on {contact.net}"
            )
        matched.add(matches[0])
        pairs.append((source[matches[0]], contact))
    return tuple(pairs)


def _require_ipc356_source_via_dimensions(pairs: tuple[tuple[SourceVia, Contact], ...]) -> None:
    """Compare matched circular source vias with their IPC-D-356 dimensions."""
    mismatches: list[str] = []
    for via, contact in pairs:
        if via.copper_diameter_nm is None:
            raise UnsupportedFabricationFormat(
                f"source via copper size is unavailable on {via.net_name}"
            )
        if contact.size_x_mm is None or contact.size_y_mm is None:
            raise UnsupportedFabricationFormat(
                f"IPC-D-356 VIA dimensions are unavailable on {contact.net}"
            )
        observed_x_nm = round(contact.size_x_mm * _NM_PER_MM)
        observed_y_nm = round(contact.size_y_mm * _NM_PER_MM)
        tolerance_nm = contact.coordinate_resolution_nm // 2 + 1
        if (
            abs(observed_x_nm - via.copper_diameter_nm) > tolerance_nm
            or abs(observed_y_nm) > tolerance_nm
        ):
            mismatches.append(
                f"{contact.net} exports VIA size ({observed_x_nm}, {observed_y_nm}) nm; "
                f"expected ({via.copper_diameter_nm}, 0) nm"
            )
    if mismatches:
        raise UnsupportedFabricationFormat(
            "IPC-D-356 VIA dimensions differ from source PCB via geometry: "
            + "; ".join(sorted(mismatches))
        )


def _is_via(contact: Contact) -> bool:
    return contact.reference.casefold() == "via" and contact.pin.casefold() == "via"


def _via_contact(contact: Contact) -> Contact:
    if contact.net.startswith("N/C:"):
        raise UnsupportedFabricationFormat("IPC-D-356 VIA contact has no named net")
    return contact


def _contact_key(contact: Contact) -> tuple[str, float, float]:
    return contact.net, contact.x_mm, contact.y_mm
