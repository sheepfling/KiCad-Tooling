"""Source-bound review candidates for unassigned copper pads in active footprints."""

from __future__ import annotations

from bisect import bisect_right
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .kicad_sexpr import SExprSpan, sexpr_atoms, sexpr_children, sexpr_nodes, sexpr_root
from .netlist_contract_models import NetlistContract
from .pcb_board_source_binding import (
    read_source_bound_pcb_board,
    verify_source_bound_pcb_board_unchanged,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.unassigned_copper_pad_review"
_SUPPORTED_KICAD_VERSIONS = frozenset({"10.0.0", "10.0.5"})


def unassigned_copper_pad_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
    netlist: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review unassigned copper pads that the schematic pin inventory cannot identify."""
    if config.kind is not ProjectKind.PCB or config.kicad_version not in _SUPPORTED_KICAD_VERSIONS:
        return ()
    board = read_source_bound_pcb_board(root, config, source_hashes)
    if board is None:
        return ()
    try:
        document = board.source.decode("utf-8")
        board_root = sexpr_root(document, "kicad_pcb")
    except (UnicodeError, ValueError):
        return ()

    line_breaks = tuple(index for index, character in enumerate(document) if character == "\n")
    pin_numbers_by_reference = {
        reference.casefold(): frozenset(numbers)
        for reference, numbers in netlist.component_pin_numbers.items()
    }
    candidates: list[Candidate] = []
    for footprint in sexpr_children(document, board_root.start + 1, board_root.end - 1):
        if sexpr_atoms(document, footprint)[:1] != ("footprint",):
            continue
        attribute_flags = {
            flag
            for node in sexpr_nodes(document, footprint, "attr")
            for flag in sexpr_atoms(document, node)[1:]
        }
        if attribute_flags & {"dnp", "board_only"}:
            continue
        reference = _footprint_reference(document, footprint)
        if reference is None:
            continue
        schematic_pin_numbers = pin_numbers_by_reference.get(reference.casefold())
        if schematic_pin_numbers is None:
            continue
        pads = tuple(
            pad
            for pad in sexpr_nodes(document, footprint, "pad")
            if _has_copper_layer(document, pad)
        )
        pad_states = tuple(
            (pad, _pad_number(document, pad), _pad_net_state(document, pad)) for pad in pads
        )
        if any(assigned is None for _pad, _number, assigned in pad_states):
            continue
        pad_number_counts: dict[str, int] = {}
        for _pad, number, _assigned in pad_states:
            if number:
                pad_number_counts[number] = pad_number_counts.get(number, 0) + 1
        if not any(assigned is True for _pad, _number, assigned in pad_states):
            continue
        assigned_numbers = tuple(
            sorted({number for _pad, number, assigned in pad_states if number and assigned is True})
        )
        for pad_index, (pad, number, assigned) in enumerate(pad_states, start=1):
            if assigned is not False:
                continue
            if number and (pad_number_counts[number] != 1 or number in schematic_pin_numbers):
                continue
            line = bisect_right(line_breaks, pad.start) + 1
            subject_pad = number if number else f"unnumbered-copper-pad-{pad_index}"
            message = (
                f"PCB footprint {reference} has unnumbered copper pad {pad_index} with no "
                "assigned net while other copper pads in the footprint are netted. Review "
                "whether this is an intentional mechanical/contact pad or an omitted pad "
                "assignment."
                if not number
                else f"PCB footprint {reference} has copper pad {number} with no assigned net "
                "while other copper pads in the footprint are netted and that pad number is "
                "absent from the schematic pin inventory. Confirm whether this is an intentional "
                "NC/mechanical pad or a missing footprint-to-symbol mapping."
            )
            evidence = {
                "source_path": (board.relative_path,),
                "source_sha256": (board.sha256,),
                "reference": (reference,),
                "pad_number": (number if number else "<unnumbered>",),
                "assigned_pad_numbers": assigned_numbers,
                "source_line": (str(line),),
            }
            if not number:
                evidence["pad_index"] = (str(pad_index),)
            candidates.append(
                Candidate(
                    rule_id=_RULE_ID,
                    subject=f"{board.relative_path}:{line}:{reference}.{subject_pad}",
                    message=message,
                    evidence=evidence,
                )
            )

    verify_source_bound_pcb_board_unchanged(board)
    return tuple(sorted(candidates, key=lambda item: item.subject.casefold()))


def _footprint_reference(document: str, footprint: SExprSpan) -> str | None:
    """Read the unique direct KiCad footprint reference property."""
    references: list[str] = []
    for node in sexpr_nodes(document, footprint, "property"):
        atoms = sexpr_atoms(document, node)
        if len(atoms) == 3 and atoms[1] == "Reference":
            references.append(atoms[2])
    if len(references) != 1 or not references[0].strip():
        return None
    return references[0]


def _pad_number(document: str, pad: SExprSpan) -> str:
    atoms = sexpr_atoms(document, pad)
    return atoms[1].strip() if len(atoms) >= 4 else ""


def _has_copper_layer(document: str, pad: SExprSpan) -> bool:
    layers = sexpr_nodes(document, pad, "layers")
    if len(layers) != 1:
        return False
    names = sexpr_atoms(document, layers[0])[1:]
    return any(name.casefold() == "*.cu" or name.casefold().endswith(".cu") for name in names)


def _pad_net_state(document: str, pad: SExprSpan) -> bool | None:
    nodes = sexpr_nodes(document, pad, "net")
    if not nodes:
        return False
    if len(nodes) != 1:
        return None
    atoms = sexpr_atoms(document, nodes[0])
    if len(atoms) != 3:
        return None
    try:
        code = int(atoms[1])
    except ValueError:
        return None
    if code == 0 and not atoms[2]:
        return False
    if code > 0 and atoms[2]:
        return True
    return None
