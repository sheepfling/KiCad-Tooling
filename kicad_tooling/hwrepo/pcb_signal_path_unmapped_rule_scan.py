"""Apply project modes and source-bound evidence to unmapped path-rule review."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .design_lint_policy_models import DesignLintPolicy
from .design_lint_types import Candidate
from .pcb_drc_rule_parser import native_constraints
from .pcb_drc_source_evidence import (
    source_bound_drc_evidence,
    verify_source_bound_drc_unchanged,
)
from .pcb_signal_path_unmapped_native import (
    RULE_ID,
    unmapped_signal_path_length_rule_candidates,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory


def scan_unmapped_signal_path_length_rules(
    root: Path,
    config: ProjectConfig,
    policy: DesignLintPolicy,
    source_hashes: SourceHashInventory,
    native_summary: Path,
    current_net_names: Mapping[str, object],
    source_netlist_sha256: str,
) -> tuple[Candidate, ...]:
    """Review exact native length-rule scopes missing from an enabled path map."""
    requirements = policy.pcb_signal_path_rule_map
    if requirements is None or config.kind is not ProjectKind.PCB:
        return ()
    if not requirements.has_native_drc_requirements():
        return ()
    coverage_mode = next(
        (item.mode for item in policy.rules if item.rule_id == "pcb.signal_path_rule_coverage"),
        "review",
    )
    unmapped_mode = next(
        (item.mode for item in policy.rules if item.rule_id == RULE_ID),
        "review",
    )
    if coverage_mode == "off" or unmapped_mode == "off":
        return ()

    evidence = source_bound_drc_evidence(root, config, source_hashes, native_summary)
    candidates = unmapped_signal_path_length_rule_candidates(
        requirements,
        native_constraints(evidence.rules_source),
        evidence,
        current_net_names=current_net_names,
        source_netlist_sha256=source_netlist_sha256,
        kicad_version=config.kicad_version,
    )
    verify_source_bound_drc_unchanged(root, config, source_hashes, evidence)
    return candidates
