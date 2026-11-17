"""Read the authoritative named-net table from a KiCad PCB source."""

from __future__ import annotations

from .kicad_sexpr import sexpr_atoms, sexpr_children, sexpr_root


def pcb_board_net_map(document: str) -> tuple[tuple[int, str], ...] | None:
    """Return the unique top-level net-code table, or ``None`` if incomplete."""
    try:
        root = sexpr_root(document, "kicad_pcb")
        children = sexpr_children(document, root.start + 1, root.end - 1)
    except ValueError:
        return None

    nets: list[tuple[int, str]] = []
    seen_codes: set[int] = set()
    seen_names: set[str] = set()
    found_net_record = False
    for child in children:
        atoms = sexpr_atoms(document, child)
        if not atoms or atoms[0] != "net":
            continue
        found_net_record = True
        if len(atoms) != 3:
            return None
        try:
            code = int(atoms[1])
        except ValueError:
            return None
        name = atoms[2]
        if code < 0 or code in seen_codes:
            return None
        seen_codes.add(code)
        if code == 0 and name == "":
            nets.append((code, name))
            continue
        if code == 0 or not name or name in seen_names:
            return None
        seen_names.add(name)
        nets.append((code, name))
    if not found_net_record:
        return None
    return tuple(sorted(nets))


def pcb_board_net_names(document: str) -> tuple[str, ...] | None:
    """Return unique top-level named nets, or ``None`` for incomplete inventory."""
    net_map = pcb_board_net_map(document)
    if net_map is None:
        return None
    return tuple(sorted(name for code, name in net_map if code > 0))
