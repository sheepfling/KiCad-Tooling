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
from .pcb_track_angle_models import PcbTrackAngleMap
from .pcb_track_angle_unmapped_geometry import (
    unavailable_acute_track_corner_candidate,
    unmapped_acute_track_corner_candidates,
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
    return config.kind is ProjectKind.PCB and (
        unmapped_acute_track_corner_mode(policy) != "off"
        or (track_angle_geometry_mode(policy) != "off" and policy.pcb_track_angle_map is not None)
    )


def unmapped_acute_track_corner_mode(policy: DesignLintPolicy) -> TrackAngleGeometryMode:
    """Return the opt-in mode for acute-corner geometry discovery."""
    override = next(
        (item for item in policy.rules if item.rule_id == "pcb.unmapped_acute_track_corner_review"),
        None,
    )
    return "off" if override is None else override.mode


def track_angle_geometry_candidates_for_scan(
    config: ProjectConfig,
    policy: DesignLintPolicy,
    source_hashes: SourceHashInventory,
    *,
    evidence: PcbGeometrySourceEvidence | None = None,
    netlist_sha256: str | None = None,
    issue: str | None = None,
) -> tuple[Candidate, ...]:
    """Return enabled mapped and acute-corner geometry candidates."""
    mapped_enabled = track_angle_geometry_mode(policy) != "off"
    acute_enabled = unmapped_acute_track_corner_mode(policy) != "off"
    if config.kind is not ProjectKind.PCB or not (mapped_enabled or acute_enabled):
        return ()
    angle_map: PcbTrackAngleMap | None = policy.pcb_track_angle_map
    candidates: list[Candidate] = []
    if mapped_enabled:
        if angle_map is None:
            candidates.append(track_angle_geometry_map_missing_candidate(config, source_hashes))
        elif issue is not None:
            candidate = track_angle_geometry_unavailable_candidate(
                config, policy, source_hashes, issue
            )
            if candidate is not None:
                candidates.append(candidate)
        elif evidence is None or netlist_sha256 is None:
            candidate = track_angle_geometry_unavailable_candidate(
                config,
                policy,
                source_hashes,
                "native PCB snapshot or source-bound netlist hash is unavailable",
            )
            if candidate is not None:
                candidates.append(candidate)
        else:
            candidates.extend(track_angle_geometry_candidates(angle_map, evidence, netlist_sha256))
    if acute_enabled:
        if issue is not None:
            candidates.append(
                unavailable_acute_track_corner_candidate(config, source_hashes, issue, angle_map)
            )
        elif evidence is None or netlist_sha256 is None:
            candidates.append(
                unavailable_acute_track_corner_candidate(
                    config,
                    source_hashes,
                    "native PCB snapshot or source-bound netlist hash is unavailable",
                    angle_map,
                )
            )
        else:
            candidates.extend(
                unmapped_acute_track_corner_candidates(angle_map, evidence, netlist_sha256)
            )
    return tuple(candidates)
