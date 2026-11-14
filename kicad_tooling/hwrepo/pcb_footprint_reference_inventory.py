"""Complete footprint-reference inventory from KiCad PCB source."""

from __future__ import annotations

from .kicad_sexpr import SExprSpan, sexpr_atoms, sexpr_children, sexpr_nodes, sexpr_root


def pcb_footprint_reference(document: str, footprint: SExprSpan) -> str | None:
    """Read one unique direct or legacy reference property from a footprint."""
    properties = tuple(
        atoms[2]
        for node in sexpr_nodes(document, footprint, "property")
        if len(atoms := sexpr_atoms(document, node)) == 3 and atoms[1] == "Reference"
    )
    if properties:
        return properties[0] if len(properties) == 1 and properties[0].strip() else None

    legacy_text = tuple(
        atoms[2]
        for node in sexpr_nodes(document, footprint, "fp_text")
        if len(atoms := sexpr_atoms(document, node)) >= 3 and atoms[1] == "reference"
    )
    if len(legacy_text) != 1 or not legacy_text[0].strip():
        return None
    return legacy_text[0]


def pcb_board_footprint_reference_names(document: str) -> tuple[str, ...] | None:
    """Return all unique, unambiguous PCB footprint references or ``None``."""
    try:
        root = sexpr_root(document, "kicad_pcb")
        children = sexpr_children(document, root.start + 1, root.end - 1)
    except ValueError:
        return None

    references: list[str] = []
    for child in children:
        if sexpr_atoms(document, child)[:1] != ("footprint",):
            continue
        reference = pcb_footprint_reference(document, child)
        if reference is None or not reference.isascii():
            return None
        references.append(reference)

    folded = tuple(reference.casefold() for reference in references)
    if len(set(folded)) != len(folded):
        return None
    return tuple(sorted(references, key=lambda value: (value.casefold(), value)))


def pcb_board_footprint_pad_number_inventory(
    document: str,
) -> tuple[tuple[str, tuple[str, ...]], ...] | None:
    """Return each unambiguous footprint reference and its complete pad-number inventory."""
    try:
        root = sexpr_root(document, "kicad_pcb")
        children = sexpr_children(document, root.start + 1, root.end - 1)
    except ValueError:
        return None

    footprints: list[tuple[str, tuple[str, ...]]] = []
    for child in children:
        if sexpr_atoms(document, child)[:1] != ("footprint",):
            continue
        reference = pcb_footprint_reference(document, child)
        if reference is None or not reference.isascii():
            return None
        pad_numbers: list[str] = []
        for pad in sexpr_nodes(document, child, "pad"):
            atoms = sexpr_atoms(document, pad)
            if len(atoms) < 4 or not atoms[1].isascii():
                return None
            pad_numbers.append(atoms[1])
        footprints.append(
            (reference, tuple(sorted(pad_numbers, key=lambda value: (value.casefold(), value))))
        )

    folded_references = tuple(reference.casefold() for reference, _ in footprints)
    if len(set(folded_references)) != len(folded_references):
        return None
    return tuple(sorted(footprints, key=lambda item: (item[0].casefold(), item[0])))
