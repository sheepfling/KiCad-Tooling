"""Bind exact custom DRC net-scope review to current PCB and native evidence."""

from __future__ import annotations

from pathlib import Path

from .design_lint_policy_models import DesignLintPolicy
from .design_lint_types import Candidate
from .pcb_board_net_inventory import pcb_board_net_names
from .pcb_drc_exact_net_scope import (
    RULE_ID,
    SUPPORTED_KICAD_VERSIONS,
    unmatched_exact_net_scope_candidates,
)
from .pcb_drc_rule_parser import native_constraints
from .pcb_drc_source_evidence import (
    source_bound_drc_evidence,
    verify_source_bound_drc_unchanged,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_SUPPORTED_PROJECT_KINDS = frozenset({ProjectKind.PCB, ProjectKind.PCB_ONLY})


def scan_unmatched_exact_net_drc_scopes(
    root: Path,
    config: ProjectConfig,
    policy: DesignLintPolicy,
    source_hashes: SourceHashInventory,
    native_summary: Path,
) -> tuple[Candidate, ...]:
    """Review exact native net scopes that are absent from the current PCB."""
    modes = {item.rule_id: item.mode for item in policy.rules}
    if (
        config.kind not in _SUPPORTED_PROJECT_KINDS
        or config.kicad_version not in SUPPORTED_KICAD_VERSIONS
        or modes.get(RULE_ID, "review") == "off"
    ):
        return ()

    evidence = source_bound_drc_evidence(root, config, source_hashes, native_summary)
    net_names = pcb_board_net_names(evidence.board_file.read_text(encoding="utf-8"))
    if net_names is None:
        verify_source_bound_drc_unchanged(root, config, source_hashes, evidence)
        return ()

    candidates = unmatched_exact_net_scope_candidates(
        native_constraints(evidence.rules_source),
        net_names,
        evidence,
        kicad_version=config.kicad_version,
    )
    verify_source_bound_drc_unchanged(root, config, source_hashes, evidence)
    return candidates
