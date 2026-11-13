"""Shared typed parsing for source-bound copper-pad identity and net state."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import Literal

from .kicad_sexpr import SExprSpan, sexpr_atoms, sexpr_children, sexpr_nodes, sexpr_root
from .pcb_board_source_binding import SourceBoundPcbBoard
from .pcb_footprint_reference_inventory import pcb_footprint_reference

PcbPadNetState = Literal["assigned", "unassigned", "unknown"]


@dataclass(frozen=True, slots=True)
class PcbCopperPadSource:
    """One copper pad's source position, number, and native net assignment."""

    number: str
    copper_ordinal: int
    source_line: int
    net_state: PcbPadNetState
    net_code: int | None = None
    net_name: str | None = None


@dataclass(frozen=True, slots=True)
class PcbFootprintPadSource:
    """Copper-pad inventory for one uniquely referenced board footprint."""

    reference: str
    dnp: bool
    board_only: bool
    pads: tuple[PcbCopperPadSource, ...]


def source_bound_pcb_footprint_pads(
    board: SourceBoundPcbBoard,
) -> tuple[PcbFootprintPadSource, ...] | None:
    """Parse copper pads from an already hash-matched PCB source file."""
    try:
        document = board.source.decode("utf-8")
        board_root = sexpr_root(document, "kicad_pcb")
    except (UnicodeError, ValueError):
        return None

    line_breaks = tuple(index for index, character in enumerate(document) if character == "\n")
    footprints: list[PcbFootprintPadSource] = []
    for footprint in sexpr_children(document, board_root.start + 1, board_root.end - 1):
        if sexpr_atoms(document, footprint)[:1] != ("footprint",):
            continue
        flags = {
            flag
            for node in sexpr_nodes(document, footprint, "attr")
            for flag in sexpr_atoms(document, node)[1:]
        }
        reference = pcb_footprint_reference(document, footprint)
        if reference is None:
            continue
        pads: list[PcbCopperPadSource] = []
        for pad in sexpr_nodes(document, footprint, "pad"):
            if not _has_copper_layer(document, pad):
                continue
            state, code, name = _pad_net_assignment(document, pad)
            atoms = sexpr_atoms(document, pad)
            pads.append(
                PcbCopperPadSource(
                    number=atoms[1].strip() if len(atoms) >= 4 else "",
                    copper_ordinal=len(pads) + 1,
                    source_line=bisect_right(line_breaks, pad.start) + 1,
                    net_state=state,
                    net_code=code,
                    net_name=name,
                )
            )
        footprints.append(
            PcbFootprintPadSource(
                reference=reference,
                dnp="dnp" in flags,
                board_only="board_only" in flags,
                pads=tuple(pads),
            )
        )
    return tuple(footprints)


def _has_copper_layer(document: str, pad: SExprSpan) -> bool:
    layers = sexpr_nodes(document, pad, "layers")
    if len(layers) != 1:
        return False
    names = sexpr_atoms(document, layers[0])[1:]
    return any(name.casefold() == "*.cu" or name.casefold().endswith(".cu") for name in names)


def _pad_net_assignment(
    document: str,
    pad: SExprSpan,
) -> tuple[PcbPadNetState, int | None, str | None]:
    nodes = sexpr_nodes(document, pad, "net")
    if not nodes:
        return "unassigned", None, None
    if len(nodes) != 1:
        return "unknown", None, None
    atoms = sexpr_atoms(document, nodes[0])
    if len(atoms) != 3:
        return "unknown", None, None
    try:
        code = int(atoms[1])
    except ValueError:
        return "unknown", None, None
    name = atoms[2]
    if code == 0 and not name:
        return "unassigned", None, None
    if code > 0 and name:
        return "assigned", code, name
    return "unknown", None, None
