"""Source-bound review candidates for conflicting same-numbered copper pads."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .pcb_board_source_binding import (
    read_source_bound_pcb_board,
    verify_source_bound_pcb_board_unchanged,
)
from .pcb_pad_source import PcbCopperPadSource, source_bound_pcb_footprint_pads
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.duplicate_pad_net_conflict"
_SUPPORTED_KICAD_VERSIONS = frozenset({"10.0.0", "10.0.5"})


def duplicate_pad_net_conflict_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
    netlist: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review schematic-backed duplicate pad numbers assigned to different nets."""
    if config.kind is not ProjectKind.PCB or config.kicad_version not in _SUPPORTED_KICAD_VERSIONS:
        return ()
    board = read_source_bound_pcb_board(root, config, source_hashes)
    if board is None:
        return ()
    footprints = source_bound_pcb_footprint_pads(board)
    if footprints is None:
        return ()

    schematic_pins = {
        reference.casefold(): frozenset(numbers)
        for reference, numbers in netlist.component_pin_numbers.items()
    }
    dnp_references = {reference.casefold() for reference in netlist.dnp_components}
    reference_counts = Counter(item.reference.casefold() for item in footprints)
    candidates: list[Candidate] = []
    for footprint in footprints:
        reference_key = footprint.reference.casefold()
        if (
            footprint.dnp
            or footprint.board_only
            or reference_key in dnp_references
            or reference_counts[reference_key] != 1
        ):
            continue
        known_pin_numbers = schematic_pins.get(reference_key)
        if known_pin_numbers is None:
            continue
        pads_by_number: dict[str, list[PcbCopperPadSource]] = defaultdict(list)
        for pad in footprint.pads:
            if pad.number and pad.number in known_pin_numbers:
                pads_by_number[pad.number].append(pad)
        for number, pads in sorted(pads_by_number.items()):
            if len(pads) < 2 or any(pad.net_state == "unknown" for pad in pads):
                continue
            assignments = {_pad_assignment_key(pad) for pad in pads}
            if len(assignments) < 2:
                continue
            pad_assignments = tuple(
                _pad_assignment_evidence(pad)
                for pad in sorted(pads, key=lambda item: item.copper_ordinal)
            )
            source_line = min(pad.source_line for pad in pads)
            candidates.append(
                Candidate(
                    rule_id=_RULE_ID,
                    subject=(f"{board.relative_path}:{source_line}:{footprint.reference}.{number}"),
                    message=(
                        f"PCB footprint {footprint.reference} has multiple copper pads numbered "
                        f"{number} with different net assignments. Review whether all physical "
                        "pads for this schematic pin should share one net or have an explicitly "
                        "reviewed footprint exception."
                    ),
                    evidence={
                        "source_path": (board.relative_path,),
                        "source_sha256": (board.sha256,),
                        "reference": (footprint.reference,),
                        "pad_number": (number,),
                        "schematic_pin": (f"{footprint.reference}.{number}",),
                        "pad_assignments": pad_assignments,
                    },
                )
            )

    verify_source_bound_pcb_board_unchanged(board)
    return tuple(sorted(candidates, key=lambda item: item.subject.casefold()))


def _pad_assignment_key(pad: PcbCopperPadSource) -> tuple[str, int | None, str | None]:
    if pad.net_state == "unassigned":
        return ("unassigned", None, None)
    return (pad.net_state, pad.net_code, pad.net_name)


def _pad_assignment_evidence(pad: PcbCopperPadSource) -> str:
    if pad.net_state == "unassigned":
        assignment = "<unassigned>"
    elif pad.net_state == "assigned":
        assignment = f"{pad.net_code}:{pad.net_name}"
    else:
        assignment = "<unknown>"
    return f"pad {pad.copper_ordinal}, line {pad.source_line}: {assignment}"
