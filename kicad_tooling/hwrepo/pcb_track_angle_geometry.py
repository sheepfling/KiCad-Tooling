"""Review unambiguous routed corners against authored PCB angle bounds."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees
from pathlib import Path

from .design_lint_pcb_coverage_common import PcbGeometrySourceEvidence, map_sha256
from .design_lint_policy_models import DesignLintPolicy
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .pcb_connectivity_observations import PcbTrackObservation
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_track_angle_models import PcbTrackAngleMap, PcbTrackAngleRequirement
from .project_models import ProjectConfig
from .source_state_models import SourceHashInventory

RULE_ID: DesignLintRuleId = "pcb.track_angle_geometry_review"
_SUPPORTED_KICAD_VERSIONS = frozenset({"10.0.0", "10.0.5"})


@dataclass(frozen=True, slots=True)
class PcbTrackAngleCorner:
    """One measured, reciprocal segment-to-segment native endpoint corner."""

    requirement: PcbTrackAngleRequirement
    first_track_uuid: str
    second_track_uuid: str
    layer: str
    vertex_nm: tuple[int, int]
    angle_millidegrees: int
    bound_issue: str | None


@dataclass(frozen=True, slots=True)
class _Endpoint:
    point_nm: tuple[int, int]
    other_nm: tuple[int, int]
    pads: tuple[str, ...]
    vias: tuple[str, ...]
    tracks: tuple[str, ...]


def _endpoints(track: PcbTrackObservation) -> tuple[_Endpoint, _Endpoint]:
    return (
        _Endpoint(
            point_nm=track.start_nm,
            other_nm=track.end_nm,
            pads=track.start_pads,
            vias=track.start_vias,
            tracks=track.start_tracks,
        ),
        _Endpoint(
            point_nm=track.end_nm,
            other_nm=track.start_nm,
            pads=track.end_pads,
            vias=track.end_vias,
            tracks=track.end_tracks,
        ),
    )


def _measured_angle_millidegrees(
    vertex: tuple[int, int], first: tuple[int, int], second: tuple[int, int]
) -> int | None:
    first_vector = (first[0] - vertex[0], first[1] - vertex[1])
    second_vector = (second[0] - vertex[0], second[1] - vertex[1])
    if first_vector == (0, 0) or second_vector == (0, 0):
        return None
    dot = first_vector[0] * second_vector[0] + first_vector[1] * second_vector[1]
    cross = abs(first_vector[0] * second_vector[1] - first_vector[1] * second_vector[0])
    return round(degrees(atan2(cross, dot)) * 1000)


def _bound_issue(requirement: PcbTrackAngleRequirement, angle_millidegrees: int) -> str | None:
    if (
        requirement.minimum_degrees is not None
        and angle_millidegrees < requirement.minimum_degrees * 1000
    ):
        return f"below the configured {requirement.minimum_degrees} degree minimum"
    if (
        requirement.maximum_degrees is not None
        and angle_millidegrees > requirement.maximum_degrees * 1000
    ):
        return f"above the configured {requirement.maximum_degrees} degree maximum"
    return None


def _reciprocal_neighbor(
    track: PcbTrackObservation,
    endpoint: _Endpoint,
    tracks_by_id: dict[str, PcbTrackObservation],
) -> tuple[PcbTrackObservation, _Endpoint] | None:
    if track.geometry_kind != "segment" or endpoint.pads or endpoint.vias:
        return None
    if len(endpoint.tracks) != 1:
        return None
    neighbor = tracks_by_id.get(endpoint.tracks[0].casefold())
    if (
        neighbor is None
        or neighbor.geometry_kind != "segment"
        or neighbor.net is None
        or track.net is None
        or neighbor.net.casefold() != track.net.casefold()
        or neighbor.layer.casefold() != track.layer.casefold()
    ):
        return None
    matches = tuple(
        candidate
        for candidate in _endpoints(neighbor)
        if candidate.point_nm == endpoint.point_nm
        and not candidate.pads
        and not candidate.vias
        and len(candidate.tracks) == 1
        and candidate.tracks[0].casefold() == track.uuid.casefold()
    )
    return (neighbor, matches[0]) if len(matches) == 1 else None


def track_angle_geometry_violations(
    angle_map: PcbTrackAngleMap, snapshot: PcbConnectivitySnapshot
) -> tuple[PcbTrackAngleCorner, ...]:
    """Measure mapped corners only when native endpoint topology is reciprocal and simple."""
    if int(snapshot.schema_version) < 8:
        raise ValueError("PCB track-angle geometry requires native endpoint-contact schema 8+")
    requirements = {item.net.casefold(): item for item in angle_map.requirements}
    tracks_by_id = {item.uuid.casefold(): item for item in snapshot.tracks}
    found: list[PcbTrackAngleCorner] = []
    seen: set[tuple[str, str, tuple[int, int]]] = set()
    for track in sorted(snapshot.tracks, key=lambda item: item.uuid.casefold()):
        if track.net is None or track.net.casefold() not in requirements:
            continue
        requirement = requirements[track.net.casefold()]
        for endpoint in _endpoints(track):
            neighbor_pair = _reciprocal_neighbor(track, endpoint, tracks_by_id)
            if neighbor_pair is None:
                continue
            neighbor, neighbor_endpoint = neighbor_pair
            corner_key = (
                min(track.uuid.casefold(), neighbor.uuid.casefold()),
                max(track.uuid.casefold(), neighbor.uuid.casefold()),
                endpoint.point_nm,
            )
            if corner_key in seen:
                continue
            seen.add(corner_key)
            angle = _measured_angle_millidegrees(
                endpoint.point_nm,
                endpoint.other_nm,
                neighbor_endpoint.other_nm,
            )
            if angle is None:
                continue
            issue = _bound_issue(requirement, angle)
            if issue is not None:
                first_uuid, second_uuid = sorted((track.uuid, neighbor.uuid), key=str.casefold)
                found.append(
                    PcbTrackAngleCorner(
                        requirement=requirement,
                        first_track_uuid=first_uuid,
                        second_track_uuid=second_uuid,
                        layer=track.layer,
                        vertex_nm=endpoint.point_nm,
                        angle_millidegrees=angle,
                        bound_issue=issue,
                    )
                )
    return tuple(
        sorted(
            found,
            key=lambda item: (
                item.requirement.net.casefold(),
                item.layer.casefold(),
                item.vertex_nm,
                item.first_track_uuid.casefold(),
                item.second_track_uuid.casefold(),
            ),
        )
    )


def _corner_candidate(
    corner: PcbTrackAngleCorner,
    evidence: PcbGeometrySourceEvidence,
    netlist_sha256: str,
    requirements: PcbTrackAngleMap,
) -> Candidate:
    angle_text = f"{corner.angle_millidegrees / 1000:.3f}"
    requirement = corner.requirement
    subject = (
        f"{requirement.net} {corner.layer} corner at {corner.vertex_nm[0]},{corner.vertex_nm[1]} nm"
    )
    minimum = "<none>" if requirement.minimum_degrees is None else str(requirement.minimum_degrees)
    maximum = "<none>" if requirement.maximum_degrees is None else str(requirement.maximum_degrees)
    return Candidate(
        rule_id=RULE_ID,
        subject=subject,
        message=f"Measured {angle_text} degree corner is {corner.bound_issue}.",
        evidence={
            "net": (requirement.net,),
            "requirement_id": (requirement.id,),
            "requirement_basis": (requirement.basis,),
            "angle_bounds_degrees": (f"minimum={minimum};maximum={maximum}",),
            "measured_angle_degrees": (angle_text,),
            "measurement_resolution_degrees": ("0.001",),
            "track_uuids": (corner.first_track_uuid, corner.second_track_uuid),
            "layer": (corner.layer,),
            "vertex_nm": (f"{corner.vertex_nm[0]},{corner.vertex_nm[1]}",),
            "board_path": (evidence.board_path,),
            "board_sha256": (evidence.board_sha256,),
            "snapshot_path": (evidence.snapshot_relative_path,),
            "snapshot_sha256": (evidence.snapshot_sha256,),
            "probe_sha256": (evidence.probe_sha256,),
            "kicad_version": (evidence.snapshot.kicad_version,),
            "image": (evidence.snapshot.image,),
            "netlist_sha256": (netlist_sha256,),
            "angle_map_sha256": (map_sha256(requirements),),
            "scope": (
                (
                    "reciprocal, same-net, same-layer endpoint contacts between two straight segments; "
                    "ambiguous junctions, pad/via contacts, and arcs are skipped"
                ),
            ),
        },
    )


def track_angle_geometry_candidates(
    angle_map: PcbTrackAngleMap,
    evidence: PcbGeometrySourceEvidence,
    netlist_sha256: str,
) -> tuple[Candidate, ...]:
    """Project exact geometry mismatches into source-bound design-lint findings."""
    if evidence.snapshot.kicad_version not in _SUPPORTED_KICAD_VERSIONS:
        return (
            _capture_unavailable_candidate(
                board_path=evidence.board_path,
                board_sha256=evidence.board_sha256,
                angle_map=angle_map,
                issue=(
                    "Direct track-angle geometry has only been validated on KiCad 10.0.0 and 10.0.5; "
                    f"observed {evidence.snapshot.kicad_version}"
                ),
                kicad_version=evidence.snapshot.kicad_version,
                image=evidence.snapshot.image,
            ),
        )
    return tuple(
        _corner_candidate(corner, evidence, netlist_sha256, angle_map)
        for corner in track_angle_geometry_violations(angle_map, evidence.snapshot)
    )


def _capture_unavailable_candidate(
    *,
    board_path: str,
    board_sha256: str,
    angle_map: PcbTrackAngleMap,
    issue: str,
    kicad_version: str,
    image: str,
) -> Candidate:
    return Candidate(
        rule_id=RULE_ID,
        subject="mapped PCB track-angle geometry",
        message=f"Track-angle geometry review is incomplete: {issue}.",
        evidence={
            "coverage_status": ("INCOMPLETE",),
            "issue": (issue,),
            "board_path": (board_path,),
            "board_sha256": (board_sha256,),
            "kicad_version": (kicad_version,),
            "image": (image,),
            "angle_map_sha256": (map_sha256(angle_map),),
        },
    )


def track_angle_geometry_unavailable_candidate(
    config: ProjectConfig,
    policy: DesignLintPolicy,
    source_hashes: SourceHashInventory,
    issue: str,
) -> Candidate | None:
    """Report that an explicitly enabled geometry review could not capture native evidence."""
    angle_map = policy.pcb_track_angle_map
    if angle_map is None:
        return None
    board_path = Path(config.project).with_suffix(".kicad_pcb").as_posix()
    return _capture_unavailable_candidate(
        board_path=board_path,
        board_sha256=source_hashes.get(board_path, "<unavailable>"),
        angle_map=angle_map,
        issue=issue,
        kicad_version=config.kicad_version,
        image=config.image,
    )


def track_angle_geometry_map_missing_candidate(
    config: ProjectConfig, source_hashes: SourceHashInventory
) -> Candidate:
    """Ask for an explicit map when a project turns this opt-in rule on without scope."""
    source_path = Path(config.project).as_posix()
    return Candidate(
        rule_id=RULE_ID,
        subject="project-authored track-angle requirements",
        message=(
            "Track-angle geometry review is enabled, but no pcb_track_angle_map identifies "
            "the nets and reviewed angle limits to check."
        ),
        evidence={
            "coverage_status": ("INCOMPLETE",),
            "project_path": (source_path,),
            "project_sha256": (source_hashes.get(source_path, "<unavailable>"),),
        },
    )
