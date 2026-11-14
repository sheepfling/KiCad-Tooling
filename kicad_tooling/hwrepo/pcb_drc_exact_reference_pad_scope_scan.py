"""Bind exact custom DRC reference-and-pad scope review to current PCB evidence."""

from __future__ import annotations

from pathlib import Path

from .design_lint_policy_models import DesignLintPolicy
from .design_lint_types import Candidate
from .pcb_drc_exact_reference_pad_scope import (
    RULE_ID,
    SUPPORTED_KICAD_VERSIONS,
    unmatched_exact_reference_pad_scope_candidates,
)
from .pcb_drc_rule_parser import native_constraints
from .pcb_drc_source_evidence import (
    source_bound_drc_evidence,
    verify_source_bound_drc_unchanged,
)
from .pcb_footprint_reference_inventory import pcb_board_footprint_pad_number_inventory
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_SUPPORTED_PROJECT_KINDS = frozenset({ProjectKind.PCB, ProjectKind.PCB_ONLY})


def scan_unmatched_exact_reference_pad_drc_scopes(
    root: Path,
    config: ProjectConfig,
    policy: DesignLintPolicy,
    source_hashes: SourceHashInventory,
    native_summary: Path,
) -> tuple[Candidate, ...]:
    """Review exact native DRC footprint-reference/pad scopes absent from the board."""
    modes = {item.rule_id: item.mode for item in policy.rules}
    if (
        config.kind not in _SUPPORTED_PROJECT_KINDS
        or config.kicad_version not in SUPPORTED_KICAD_VERSIONS
        or modes.get(RULE_ID, "review") == "off"
    ):
        return ()

    evidence = source_bound_drc_evidence(root, config, source_hashes, native_summary)
    try:
        board_source = evidence.board_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        verify_source_bound_drc_unchanged(root, config, source_hashes, evidence)
        return ()
    footprint_pads = pcb_board_footprint_pad_number_inventory(board_source)
    if footprint_pads is None:
        verify_source_bound_drc_unchanged(root, config, source_hashes, evidence)
        return ()

    candidates = unmatched_exact_reference_pad_scope_candidates(
        native_constraints(evidence.rules_source),
        footprint_pads,
        evidence,
        kicad_version=config.kicad_version,
    )
    verify_source_bound_drc_unchanged(root, config, source_hashes, evidence)
    return candidates
