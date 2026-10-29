"""Review source-bound KiCad rules for project-authored courtyard edge limits."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

from .design_lint_policy_models import DesignLintPolicy
from .design_lint_types import Candidate
from .pcb_drc_rule_parser import (
    NativeRuleConstraint,
    native_clearance_limit_issue,
    native_constraints,
)
from .pcb_drc_source_evidence import (
    source_bound_drc_evidence,
    verify_source_bound_drc_unchanged,
)
from .pcb_mechanical_edge_models import PcbMechanicalEdgeClearanceRequirement
from .project_models import (
    ProjectConfig,
    ProjectKind,
)

RULE_ID = "pcb.mechanical_edge_clearance_rule_coverage"
_EDGE_CONDITION = "B.Layer == 'Edge.Cuts'"


def mechanical_edge_rule_coverage_issue(
    requirement: PcbMechanicalEdgeClearanceRequirement,
    constraints: tuple[NativeRuleConstraint, ...],
    *,
    kicad_version: str | None = None,
) -> str | None:
    if any(item.name == "unresolved_text_variable" for item in constraints):
        return "Native DRC rule text contains a text variable substitution this audit does not evaluate."
    named = tuple(
        item
        for item in constraints
        if item.rule_name.casefold() == requirement.rule_name.casefold()
    )
    if not named:
        return "The named native DRC rule is missing."

    physical = tuple(item for item in named if item.name == "physical_clearance")
    if not physical:
        return "The named native DRC rule has no physical_clearance constraint."
    if len(physical) != 1:
        return "The named native DRC rule has multiple physical_clearance constraints."

    competing = tuple(
        item
        for item in constraints
        if item.name == "physical_clearance"
        and item.layer == requirement.courtyard_layer
        and item.condition == _EDGE_CONDITION
        and item.rule_name.casefold() != requirement.rule_name.casefold()
    )
    if competing:
        names = ", ".join(sorted({item.rule_name for item in competing}))
        return f"Other native rules target the same courtyard-edge scope: {names}."

    item = physical[0]
    if item.issue is not None:
        return item.issue
    if item.severity_issue is not None:
        return item.severity_issue
    if item.severity == "ignore":
        return "The native DRC rule explicitly ignores matching courtyard-edge violations."
    if item.severity in {"warning", "exclusion"}:
        return f"The native DRC rule severity is {item.severity!r}, not a blocking error."
    if item.condition != _EDGE_CONDITION or item.layer != requirement.courtyard_layer:
        return (
            "The native rule does not target the exact board edge and courtyard layer "
            "declared by the project."
        )
    if item.minimum_nm != requirement.minimum_clearance_nm or item.maximum_nm is not None:
        return "The native physical-clearance bound differs from the project minimum."
    limit_issue = native_clearance_limit_issue(requirement.minimum_clearance_nm)
    if limit_issue is not None:
        return limit_issue
    opposite_layer = (
        "B.Courtyard" if requirement.courtyard_layer == "F.Courtyard" else "F.Courtyard"
    )
    later = tuple(
        other
        for other in constraints
        if other.name == "physical_clearance"
        and other.ordinal > item.ordinal
        and not (other.layer == opposite_layer and other.issue is None)
    )
    if later:
        names = ", ".join(f"{other.rule_name} (rule {other.ordinal})" for other in later)
        return f"Later native physical-clearance rules may override this scope: {names}."
    radius_rules = tuple(
        other
        for other in constraints
        if other.name in {"physical_clearance", "physical_hole_clearance"}
    )
    if any(not other.condition and not other.condition_unconditional for other in radius_rules):
        return "A physical-clearance rule has an unsupported or empty condition clause."
    unconditional = tuple(other for other in radius_rules if other.condition_unconditional)
    if any(other.issue is not None or other.minimum_nm is None for other in unconditional):
        return "The unconditional physical-clearance search radius cannot be determined."
    if unconditional:
        radius = max(other.minimum_nm or 0 for other in unconditional)
        if radius < requirement.minimum_clearance_nm:
            return (
                "The unconditional physical-clearance search radius is below the project minimum."
            )
    elif kicad_version != "10.0.5":
        return (
            "Conditional-only physical-clearance coverage is not established for this KiCad "
            "version; require a sufficient unconditional physical-clearance search radius."
        )
    return None


def mechanical_edge_rule_coverage_candidates(
    root: Path,
    config: ProjectConfig,
    policy: DesignLintPolicy,
    source_hashes: Mapping[str, str],
    native_summary: Path,
) -> tuple[Candidate, ...]:
    """Emit REVIEW candidates when exact courtyard-to-board-edge DRC rules are absent."""
    requirements = policy.pcb_mechanical_edge_clearance_map
    if requirements is None or config.kind is not ProjectKind.PCB:
        return ()
    mode = next(
        (item.mode for item in policy.rules if item.rule_id == RULE_ID),
        "review",
    )
    if mode == "off":
        return ()

    evidence = source_bound_drc_evidence(root, config, dict(source_hashes), native_summary)
    constraints = native_constraints(evidence.rules_source)
    map_sha256 = hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
    candidates: list[Candidate] = []
    for requirement in requirements.requirements:
        issue = mechanical_edge_rule_coverage_issue(
            requirement, constraints, kicad_version=config.kicad_version
        )
        if issue is None:
            continue
        matching = tuple(
            item
            for item in constraints
            if item.rule_name.casefold() == requirement.rule_name.casefold()
        )
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{requirement.id}: {requirement.courtyard_layer} board-edge rule",
                message=(
                    f"The project-authored {requirement.minimum_clearance_nm} nm minimum for "
                    f"{requirement.courtyard_layer} courtyard geometry does not have confirmed, "
                    f"unambiguous source-bound native DRC coverage: {issue} Review the custom "
                    "rule and rerun native DRC. This check verifies rule coverage; KiCad DRC "
                    "measures board geometry."
                ),
                evidence={
                    "requirement_id": (requirement.id,),
                    "requirement_basis": (requirement.basis,),
                    "map_sha256": (map_sha256,),
                    "rule_name": (requirement.rule_name,),
                    "courtyard_layer": (requirement.courtyard_layer,),
                    "expected_condition": (_EDGE_CONDITION,),
                    "expected_minimum_clearance_nm": (str(requirement.minimum_clearance_nm),),
                    "observed_condition": tuple(sorted({item.condition for item in matching})),
                    "observed_layers": tuple(
                        sorted({item.layer or "<missing>" for item in matching})
                    ),
                    "observed_constraint_bounds": tuple(
                        sorted(
                            f"{item.name}:min={item.minimum_nm};max={item.maximum_nm}"
                            for item in matching
                        )
                    ),
                    "observed_severities": tuple(
                        sorted({item.severity or "<default>" for item in matching})
                    ),
                    "source_path": (evidence.rules_path,),
                    "source_sha256": (evidence.rules_sha256 or "<rules-file-absent>",),
                    "board_path": (evidence.board_path,),
                    "board_sha256": (evidence.board_sha256,),
                    "native_drc_path": (evidence.native_drc_path,),
                    "native_drc_sha256": (evidence.native_drc_sha256,),
                    "native_drc_kicad_version": (config.kicad_version,),
                    "native_summary_path": (evidence.native_summary_path,),
                    "native_summary_sha256": (evidence.native_summary_sha256,),
                    "coverage_issue": (issue,),
                },
            )
        )
    verify_source_bound_drc_unchanged(root, config, dict(source_hashes), evidence)
    return tuple(candidates)
