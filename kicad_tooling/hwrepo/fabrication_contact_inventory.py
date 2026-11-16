"""Match IPC-D-356 component contacts to net-assigned source PCB pads."""

from __future__ import annotations

from collections import Counter

from .fabrication_artwork import Contact, UnsupportedFabricationFormat
from .kicad_sexpr import sexpr_atoms, sexpr_nodes, sexpr_root
from .pcb_footprint_reference_inventory import pcb_footprint_reference

_ContactKey = tuple[str, str, str]
_UnassignedPadKey = tuple[str, str]


def require_ipc356_source_pad_inventory(board_text: str, contacts: tuple[Contact, ...]) -> None:
    """Fail closed when IPC-D-356 omits, adds, or reassigns a component pad."""
    try:
        root = sexpr_root(board_text, "kicad_pcb")
    except ValueError as exc:
        raise UnsupportedFabricationFormat("board source has no unique PCB root") from exc

    assigned: Counter[_ContactKey] = Counter()
    unassigned: Counter[_UnassignedPadKey] = Counter()
    references: set[str] = set()
    assignments_by_pad: dict[_UnassignedPadKey, str | None] = {}
    for footprint in sexpr_nodes(board_text, root, "footprint"):
        reference = pcb_footprint_reference(board_text, footprint)
        if reference is None or not reference.isascii():
            raise UnsupportedFabricationFormat(
                "source board has a footprint with no unique ASCII reference"
            )
        reference_key = reference.casefold()
        if reference_key == "via" or reference_key in references:
            raise UnsupportedFabricationFormat(
                "source board has a duplicate or reserved footprint reference"
            )
        references.add(reference_key)
        for pad in sexpr_nodes(board_text, footprint, "pad"):
            atoms = sexpr_atoms(board_text, pad)
            if len(atoms) < 4 or not atoms[1] or not atoms[1].isascii():
                raise UnsupportedFabricationFormat(
                    f"source board has an unsupported pad identity on {reference}"
                )
            pad_number = atoms[1]
            pad_key = (reference_key, pad_number)
            net_nodes = sexpr_nodes(board_text, pad, "net")
            if len(net_nodes) > 1:
                raise UnsupportedFabricationFormat(
                    f"source board has multiple net assignments for {reference}.{pad_number}"
                )
            net_name: str | None = None
            if net_nodes:
                net_atoms = sexpr_atoms(board_text, net_nodes[0])
                if len(net_atoms) != 3:
                    raise UnsupportedFabricationFormat(
                        f"source board has a malformed net assignment for {reference}.{pad_number}"
                    )
                try:
                    net_code = int(net_atoms[1])
                except ValueError as exc:
                    raise UnsupportedFabricationFormat(
                        f"source board has a malformed net code for {reference}.{pad_number}"
                    ) from exc
                if net_code < 0 or (net_code == 0 and net_atoms[2]):
                    raise UnsupportedFabricationFormat(
                        f"source board has an unsupported net assignment for {reference}.{pad_number}"
                    )
                if net_code:
                    if not net_atoms[2]:
                        raise UnsupportedFabricationFormat(
                            f"source board has an unnamed net for {reference}.{pad_number}"
                        )
                    net_name = net_atoms[2]
            if pad_key in assignments_by_pad and assignments_by_pad[pad_key] != net_name:
                raise UnsupportedFabricationFormat(
                    f"source board assigns duplicate pad identity {reference}.{pad_number} to different nets"
                )
            assignments_by_pad[pad_key] = net_name
            if net_name is None:
                unassigned[pad_key] += 1
            else:
                assigned[(reference_key, pad_number, net_name)] += 1

    observed_assigned: Counter[_ContactKey] = Counter()
    observed_unassigned: Counter[_UnassignedPadKey] = Counter()
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
