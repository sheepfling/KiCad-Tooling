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
    """A source PCB via's named net and board-space drill center."""

    net_name: str
    x_nm: int
    y_nm: int


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
            position = sexpr_field(board_text, via, "at")
            if len(position) != 2:
                raise UnsupportedFabricationFormat("source via has an unsupported position")
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


def _is_via(contact: Contact) -> bool:
    return contact.reference.casefold() == "via" and contact.pin.casefold() == "via"


def _via_contact(contact: Contact) -> Contact:
    if contact.net.startswith("N/C:"):
        raise UnsupportedFabricationFormat("IPC-D-356 VIA contact has no named net")
    return contact


def _contact_key(contact: Contact) -> tuple[str, float, float]:
    return contact.net, contact.x_mm, contact.y_mm
