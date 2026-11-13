"""Source-bound review for native track-width scopes omitted from geometry maps."""

from __future__ import annotations

from pathlib import Path

from .design_lint_policy_models import DesignLintPolicy
from .design_lint_types import Candidate
from .pcb_drc_rule_parser import native_constraints
from .pcb_drc_source_evidence import (
    source_bound_drc_evidence,
    verify_source_bound_drc_unchanged,
)
from .pcb_track_width_unmapped import unmapped_track_width_rule_candidates
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

RULE_ID = "pcb.track_width_unmapped_native_rule"
GEOMETRY_RULE_ID = "pcb.minimum_track_width"


def track_width_rule_scope_candidates(
    root: Path,
    config: ProjectConfig,
    policy: DesignLintPolicy,
    source_hashes: SourceHashInventory,
    native_summary: Path,
) -> tuple[Candidate, ...]:
    """Review exact native width-rule nets omitted from enabled geometry scope."""
    requirements = policy.pcb_track_width_map
    if requirements is None or config.kind is not ProjectKind.PCB:
        return ()
    geometry_mode = next(
        (item.mode for item in policy.rules if item.rule_id == GEOMETRY_RULE_ID),
        "review",
    )
    unmapped_mode = next(
        (item.mode for item in policy.rules if item.rule_id == RULE_ID),
        "review",
    )
    if (
        geometry_mode == "off"
        or unmapped_mode == "off"
        or any(item.net == "*" for item in requirements.requirements)
    ):
        return ()

    evidence = source_bound_drc_evidence(root, config, dict(source_hashes), native_summary)
    candidates = unmapped_track_width_rule_candidates(
        requirements,
        native_constraints(evidence.rules_source),
        evidence,
        kicad_version=config.kicad_version,
    )
    verify_source_bound_drc_unchanged(root, config, dict(source_hashes), evidence)
    return candidates
