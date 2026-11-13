"""Bind unmapped differential-pair DRC scope review to current project evidence."""

from __future__ import annotations

from pathlib import Path

from .design_lint_policy_models import DesignLintPolicy
from .design_lint_types import Candidate
from .pcb_differential_pair_unmapped import unmapped_differential_pair_rule_candidates
from .pcb_drc_rule_parser import native_constraints
from .pcb_drc_source_evidence import (
    source_bound_drc_evidence,
    verify_source_bound_drc_unchanged,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

RULE_ID = "pcb.differential_pair_unmapped_native_rule"
PAIR_COVERAGE_RULE_ID = "pcb.differential_pair_rule_coverage"


def scan_unmapped_differential_pair_rules(
    root: Path,
    config: ProjectConfig,
    policy: DesignLintPolicy,
    source_hashes: SourceHashInventory,
    native_summary: Path,
) -> tuple[Candidate, ...]:
    """Review exact native pair selectors outside an enabled authored pair map."""
    requirements = policy.pcb_differential_pair_rule_map
    if requirements is None or config.kind is not ProjectKind.PCB:
        return ()
    modes = {item.rule_id: item.mode for item in policy.rules}
    if modes.get(PAIR_COVERAGE_RULE_ID, "review") == "off" or modes.get(RULE_ID, "review") == "off":
        return ()

    evidence = source_bound_drc_evidence(root, config, source_hashes, native_summary)
    candidates = unmapped_differential_pair_rule_candidates(
        requirements,
        native_constraints(evidence.rules_source),
        evidence,
        kicad_version=config.kicad_version,
    )
    verify_source_bound_drc_unchanged(root, config, source_hashes, evidence)
    return candidates
