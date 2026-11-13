"""Verify authored per-net track-angle requirements against source-bound native DRC rules."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .design_lint_policy_models import DesignLintPolicy
from .design_lint_types import Candidate
from .pcb_drc_conditions import native_net_conditions_are_disjoint
from .pcb_drc_project_settings import (
    configured_dfm_drc_check_severities,
    pcb_drc_exclusions,
)
from .pcb_drc_rule_parser import NativeRuleConstraint, native_constraints
from .pcb_drc_source_evidence import (
    source_bound_drc_evidence,
    verify_source_bound_drc_unchanged,
)
from .pcb_track_angle_models import PcbTrackAngleRequirement
from .pcb_track_angle_unmapped import unmapped_track_angle_rule_candidates
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

RULE_ID = "pcb.track_angle_rule_coverage"
UNMAPPED_RULE_ID = "pcb.track_angle_unmapped_native_rule"
GEOMETRY_RULE_ID = "pcb.track_angle_geometry_review"
_SUPPORTED_KICAD_VERSIONS = frozenset({"10.0.0", "10.0.5"})


def track_angle_rule_coverage_issue(
    requirement: PcbTrackAngleRequirement,
    constraints: tuple[NativeRuleConstraint, ...],
    project_settings: str,
    *,
    ignored_checks: frozenset[str] = frozenset(),
    kicad_version: str,
) -> str | None:
    """Return why one authored net-angle requirement lacks unambiguous DRC coverage."""
    if kicad_version not in _SUPPORTED_KICAD_VERSIONS:
        return f"Track-angle DRC coverage has not been audited for KiCad {kicad_version}."
    if any(item.name == "unresolved_text_variable" for item in constraints):
        return "Native DRC rule text has a text variable this audit does not evaluate."
    if "track_angle" in ignored_checks:
        return "The source-bound native DRC report records track_angle as ignored."
    if any(
        exclusion.marker.partition("|")[0].casefold() == "track_angle"
        for exclusion in pcb_drc_exclusions(project_settings)
    ):
        return "A source-bound track_angle DRC exclusion prevents complete coverage proof."

    named = tuple(
        item
        for item in constraints
        if item.rule_name.casefold() == requirement.rule_name.casefold()
    )
    angle_rules = tuple(item for item in named if item.name == "track_angle")
    if not angle_rules:
        return "The named native DRC rule has no track_angle constraint."
    if len(angle_rules) != 1:
        return "The named native DRC rule has multiple track_angle constraints."
    rule = angle_rules[0]
    if rule.issue is not None:
        return rule.issue
    if rule.severity_issue is not None:
        return rule.severity_issue
    expected_condition = f"A.NetName == '{requirement.net}'"
    if rule.condition != expected_condition or rule.layer is not None:
        return "The native rule does not target the exact project-authored net scope."
    if rule.minimum_angle_degrees != requirement.minimum_degrees or (
        rule.maximum_angle_degrees != requirement.maximum_degrees
    ):
        return "The native track_angle bounds differ from the project-authored degree limits."
    if rule.severity not in {None, "error"}:
        return f"The native track_angle rule severity is {rule.severity!r}, not a blocking error."

    global_track_angle = tuple(
        item
        for item in configured_dfm_drc_check_severities(project_settings)
        if item.check_id == "track_angle"
    )
    if len(global_track_angle) > 1:
        return "The project has multiple global track_angle severity declarations."
    if global_track_angle and global_track_angle[0].configured_severity != "error":
        return (
            "The global KiCad track_angle check is configured as "
            f"{global_track_angle[0].configured_severity!r}, not a blocking error."
        )

    later = tuple(
        other
        for other in constraints
        if other.name == "track_angle"
        and other.ordinal > rule.ordinal
        and not native_net_conditions_are_disjoint(rule.condition, other.condition)
    )
    if later:
        names = ", ".join(sorted({item.rule_name or "<unnamed>" for item in later}))
        return f"Later native track_angle rules may override this net scope: {names}."
    return None


def track_angle_rule_coverage_candidates(
    root: Path,
    config: ProjectConfig,
    policy: DesignLintPolicy,
    source_hashes: SourceHashInventory,
    native_summary: Path,
) -> tuple[Candidate, ...]:
    """Review mapped DRC coverage and omitted scopes used by enabled geometry lint."""
    requirements = policy.pcb_track_angle_map
    if requirements is None or config.kind is not ProjectKind.PCB:
        return ()
    coverage_mode = next((item.mode for item in policy.rules if item.rule_id == RULE_ID), "review")
    geometry_mode = next(
        (item.mode for item in policy.rules if item.rule_id == GEOMETRY_RULE_ID), "off"
    )
    unmapped_mode = next(
        (item.mode for item in policy.rules if item.rule_id == UNMAPPED_RULE_ID), "review"
    )
    review_unmapped = geometry_mode != "off" and unmapped_mode != "off"
    if coverage_mode == "off" and not review_unmapped:
        return ()

    evidence = source_bound_drc_evidence(root, config, dict(source_hashes), native_summary)
    constraints = native_constraints(evidence.rules_source)
    settings = evidence.project_file.read_text(encoding="utf-8")
    map_sha256 = hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
    candidates: list[Candidate] = []
    if coverage_mode != "off":
        for requirement in requirements.requirements:
            issue = track_angle_rule_coverage_issue(
                requirement,
                constraints,
                settings,
                ignored_checks=evidence.ignored_checks,
                kicad_version=config.kicad_version,
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
                    subject=f"{requirement.id}: {requirement.net} track-angle DRC rule",
                    message=(
                        f"The project-authored angle bounds for net {requirement.net!r} do not have "
                        "confirmed, unambiguous source-bound native DRC coverage: "
                        f"{issue} Review the custom rule and rerun native DRC."
                    ),
                    evidence={
                        "requirement_id": (requirement.id,),
                        "requirement_basis": (requirement.basis,),
                        "map_sha256": (map_sha256,),
                        "net": (requirement.net,),
                        "rule_name": (requirement.rule_name,),
                        "expected_minimum_degrees": (
                            "<none>"
                            if requirement.minimum_degrees is None
                            else str(requirement.minimum_degrees),
                        ),
                        "expected_maximum_degrees": (
                            "<none>"
                            if requirement.maximum_degrees is None
                            else str(requirement.maximum_degrees),
                        ),
                        "observed_conditions": tuple(sorted({item.condition for item in matching})),
                        "observed_angle_bounds": tuple(
                            sorted(
                                f"min={item.minimum_angle_degrees};max={item.maximum_angle_degrees}"
                                for item in matching
                            )
                        ),
                        "observed_severities": tuple(
                            sorted({item.severity or "<default>" for item in matching})
                        ),
                        "source_path": (evidence.rules_path,),
                        "source_sha256": (evidence.rules_sha256 or "<rules-file-absent>",),
                        "project_path": (evidence.project_path,),
                        "project_sha256": (evidence.project_sha256,),
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
    if review_unmapped:
        candidates.extend(
            unmapped_track_angle_rule_candidates(
                requirements,
                constraints,
                evidence,
                kicad_version=config.kicad_version,
            )
        )
    verify_source_bound_drc_unchanged(root, config, dict(source_hashes), evidence)
    return tuple(candidates)
