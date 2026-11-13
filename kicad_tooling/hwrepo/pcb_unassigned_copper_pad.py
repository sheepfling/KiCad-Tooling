"""Source-bound review candidates for unassigned copper pads in active footprints."""

from __future__ import annotations

from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .pcb_board_source_binding import (
    read_source_bound_pcb_board,
    verify_source_bound_pcb_board_unchanged,
)
from .pcb_pad_source import source_bound_pcb_footprint_pads
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
    footprints = source_bound_pcb_footprint_pads(board)
    if footprints is None:
        return ()

    pin_numbers_by_reference = {
        reference.casefold(): frozenset(numbers)
        for reference, numbers in netlist.component_pin_numbers.items()
    }
    candidates: list[Candidate] = []
    for footprint in footprints:
        if footprint.dnp or footprint.board_only:
            continue
        reference = footprint.reference
        schematic_pin_numbers = pin_numbers_by_reference.get(reference.casefold())
        if schematic_pin_numbers is None:
            continue
        if any(pad.net_state == "unknown" for pad in footprint.pads):
            continue
        pad_number_counts: dict[str, int] = {}
        for pad in footprint.pads:
            if pad.number:
                pad_number_counts[pad.number] = pad_number_counts.get(pad.number, 0) + 1
        if not any(pad.net_state == "assigned" for pad in footprint.pads):
            continue
        assigned_numbers = tuple(
            sorted(
                {pad.number for pad in footprint.pads if pad.number and pad.net_state == "assigned"}
            )
        )
        for pad in footprint.pads:
            number = pad.number
            if pad.net_state != "unassigned":
                continue
            if number and (pad_number_counts[number] != 1 or number in schematic_pin_numbers):
                continue
            line = pad.source_line
            pad_index = pad.copper_ordinal
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
