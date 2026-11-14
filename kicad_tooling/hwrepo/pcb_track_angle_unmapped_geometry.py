"""Review acute PCB track corners that lack project-authored angle scope."""

from __future__ import annotations

from pathlib import Path

from .design_lint_pcb_coverage_common import PcbGeometrySourceEvidence, map_sha256
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .pcb_track_angle_geometry import (
    SUPPORTED_TRACK_ANGLE_KICAD_VERSIONS,
    PcbTrackAngleMeasurement,
    track_angle_corner_measurements,
)
from .pcb_track_angle_models import PcbTrackAngleMap
from .project_models import ProjectConfig
from .source_state_models import SourceHashInventory

RULE_ID: DesignLintRuleId = "pcb.unmapped_acute_track_corner_review"
_ACUTE_CORNER_THRESHOLD_MILLIDEGREES = 89_000


def unmapped_acute_track_corner_candidates(
    angle_map: PcbTrackAngleMap | None,
    evidence: PcbGeometrySourceEvidence,
    netlist_sha256: str,
) -> tuple[Candidate, ...]:
    """Review bounded acute corners whose nets lack authored angle-map coverage."""
    snapshot = evidence.snapshot
    if snapshot.kicad_version not in SUPPORTED_TRACK_ANGLE_KICAD_VERSIONS:
        return (
            _unavailable_candidate(
                board_path=evidence.board_path,
                board_sha256=evidence.board_sha256,
                kicad_version=snapshot.kicad_version,
                image=snapshot.image,
                issue=(
                    "Acute-corner geometry has only been validated on KiCad 10.0.0 and 10.0.5; "
                    f"observed {snapshot.kicad_version}"
                ),
                angle_map=angle_map,
            ),
        )
    try:
        measurements = track_angle_corner_measurements(snapshot)
    except ValueError as exc:
        return (
            _unavailable_candidate(
                board_path=evidence.board_path,
                board_sha256=evidence.board_sha256,
                kicad_version=snapshot.kicad_version,
                image=snapshot.image,
                issue=str(exc),
                angle_map=angle_map,
            ),
        )
    covered_nets: set[str] = set()
    if angle_map is not None:
        covered_nets = {str(item.net).casefold() for item in angle_map.requirements}
    return tuple(
        _candidate(item, evidence, netlist_sha256, angle_map)
        for item in measurements
        if item.angle_millidegrees < _ACUTE_CORNER_THRESHOLD_MILLIDEGREES
        and item.net.casefold() not in covered_nets
    )


def unavailable_acute_track_corner_candidate(
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
    issue: str,
    angle_map: PcbTrackAngleMap | None,
) -> Candidate:
    """Report that enabled acute-corner review could not bind current PCB geometry."""
    board_path = Path(config.project).with_suffix(".kicad_pcb").as_posix()
    return _unavailable_candidate(
        board_path=board_path,
        board_sha256=source_hashes.get(board_path, "<unavailable>"),
        kicad_version=config.kicad_version,
        image=config.image,
        issue=issue,
        angle_map=angle_map,
    )


def _candidate(
    measurement: PcbTrackAngleMeasurement,
    evidence: PcbGeometrySourceEvidence,
    netlist_sha256: str,
    angle_map: PcbTrackAngleMap | None,
) -> Candidate:
    angle_text = f"{measurement.angle_millidegrees / 1000:.3f}"
    subject = (
        f"{measurement.net} {measurement.layer} corner at "
        f"{measurement.vertex_nm[0]},{measurement.vertex_nm[1]} nm"
    )
    return Candidate(
        rule_id=RULE_ID,
        subject=subject,
        message=(
            f"Measured {angle_text} degree acute corner is on a net outside the project-authored "
            "track-angle map; review whether this net needs an explicit angle requirement."
        ),
        evidence={
            "net": (measurement.net,),
            "measured_angle_degrees": (angle_text,),
            "acute_threshold_exclusive_degrees": ("89.000",),
            "track_uuids": (measurement.first_track_uuid, measurement.second_track_uuid),
            "layer": (measurement.layer,),
            "vertex_nm": (f"{measurement.vertex_nm[0]},{measurement.vertex_nm[1]}",),
            "board_path": (evidence.board_path,),
            "board_sha256": (evidence.board_sha256,),
            "snapshot_path": (evidence.snapshot_relative_path,),
            "snapshot_sha256": (evidence.snapshot_sha256,),
            "probe_sha256": (evidence.probe_sha256,),
            "kicad_version": (evidence.snapshot.kicad_version,),
            "image": (evidence.snapshot.image,),
            "netlist_sha256": (netlist_sha256,),
            "angle_map_sha256": (map_sha256(angle_map) if angle_map is not None else "<absent>",),
            "scope": (
                "only reciprocal same-net, same-layer endpoint contacts between two straight "
                + "segments; arcs, branches, mid-span contacts, and pad/via endpoints are skipped",
            ),
        },
    )


def _unavailable_candidate(
    *,
    board_path: str,
    board_sha256: str,
    kicad_version: str,
    image: str,
    issue: str,
    angle_map: PcbTrackAngleMap | None,
) -> Candidate:
    return Candidate(
        rule_id=RULE_ID,
        subject="unmapped acute PCB track-corner geometry",
        message=f"Acute track-corner review is incomplete: {issue}.",
        evidence={
            "coverage_status": ("INCOMPLETE",),
            "issue": (issue,),
            "board_path": (board_path,),
            "board_sha256": (board_sha256,),
            "kicad_version": (kicad_version,),
            "image": (image,),
            "angle_map_sha256": (map_sha256(angle_map) if angle_map is not None else "<absent>",),
        },
    )
