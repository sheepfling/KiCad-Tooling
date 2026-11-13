"""Enable and source-bind opt-in PCB track-angle geometry review."""

from __future__ import annotations

from typing import Literal

from .design_lint_pcb_coverage_common import PcbGeometrySourceEvidence
from .design_lint_policy_models import DesignLintPolicy
from .design_lint_types import Candidate
from .pcb_track_angle_geometry import (
    track_angle_geometry_candidates,
    track_angle_geometry_map_missing_candidate,
    track_angle_geometry_unavailable_candidate,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

TrackAngleGeometryMode = Literal["review", "block", "off"]


def track_angle_geometry_mode(policy: DesignLintPolicy) -> TrackAngleGeometryMode:
    override = next(
        (item for item in policy.rules if item.rule_id == "pcb.track_angle_geometry_review"),
        None,
    )
    return "off" if override is None else override.mode


def track_angle_geometry_scan_required(config: ProjectConfig, policy: DesignLintPolicy) -> bool:
    return (
        config.kind is ProjectKind.PCB
        and track_angle_geometry_mode(policy) != "off"
        and policy.pcb_track_angle_map is not None
    )


def track_angle_geometry_candidates_for_scan(
    config: ProjectConfig,
    policy: DesignLintPolicy,
    source_hashes: SourceHashInventory,
    *,
    evidence: PcbGeometrySourceEvidence | None = None,
    netlist_sha256: str | None = None,
    issue: str | None = None,
) -> tuple[Candidate, ...]:
    """Return mismatch, incomplete-evidence, or missing-map candidates for the selected mode."""
    if config.kind is not ProjectKind.PCB or track_angle_geometry_mode(policy) == "off":
        return ()
    angle_map = policy.pcb_track_angle_map
    if angle_map is None:
        return (track_angle_geometry_map_missing_candidate(config, source_hashes),)
    if issue is not None:
        candidate = track_angle_geometry_unavailable_candidate(config, policy, source_hashes, issue)
        return () if candidate is None else (candidate,)
    if evidence is None or netlist_sha256 is None:
        candidate = track_angle_geometry_unavailable_candidate(
            config,
            policy,
            source_hashes,
            "native PCB snapshot or source-bound netlist hash is unavailable",
        )
        return () if candidate is None else (candidate,)
    return track_angle_geometry_candidates(angle_map, evidence, netlist_sha256)
