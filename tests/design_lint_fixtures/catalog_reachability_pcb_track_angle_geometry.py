"""Synthetic reachability input for reviewed PCB corner-angle geometry."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.design_lint_pcb_coverage_common import PcbGeometrySourceEvidence
from kicad_tooling.hwrepo.pcb_connectivity_observations import PcbTrackObservation
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_track_angle_geometry import track_angle_geometry_candidates
from kicad_tooling.hwrepo.pcb_track_angle_models import (
    PcbTrackAngleMap,
    PcbTrackAngleRequirement,
)
from kicad_tooling.hwrepo.pcb_track_angle_unmapped_geometry import (
    unmapped_acute_track_corner_candidates,
)

_SHA = "a" * 64


def track_angle_geometry_rule_ids() -> set[str]:
    """Reach mapped and unmapped track-angle rules with synthetic corners."""
    first = PcbTrackObservation(
        uuid="00000000-0000-0000-0000-000000000001",
        net="CLOCK_OUT",
        layer="F.Cu",
        width_nm=250_000,
        start_nm=(0, 0),
        end_nm=(1_000_000, 0),
        geometry_kind="segment",
        start_pads=(),
        end_pads=(),
        start_vias=(),
        end_vias=(),
        start_tracks=(),
        end_tracks=("00000000-0000-0000-0000-000000000002",),
    )
    second = PcbTrackObservation(
        uuid="00000000-0000-0000-0000-000000000002",
        net="CLOCK_OUT",
        layer="F.Cu",
        width_nm=250_000,
        start_nm=(1_000_000, 0),
        end_nm=(2_000_000, 1_000_000),
        geometry_kind="segment",
        start_pads=(),
        end_pads=(),
        start_vias=(),
        end_vias=(),
        start_tracks=(first.uuid,),
        end_tracks=(),
    )
    snapshot = PcbConnectivitySnapshot(
        schema_version="8",
        board_sha256=_SHA,
        kicad_version="10.0.5",
        image="ghcr.io/kicad/kicad:10.0.5@sha256:" + _SHA,
        probe_sha256=_SHA,
        zones_refilled=True,
        pads=(),
        net_ties=(),
        zones=(),
        vias=(),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=(first, second),
        copper_layers=("F.Cu", "B.Cu"),
    )
    evidence = PcbGeometrySourceEvidence(
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256=_SHA,
        snapshot_relative_path="build/design-lint/reachability/snapshot.json",
        snapshot_path=Path("build/design-lint/reachability/snapshot.json"),
        snapshot_sha256=_SHA,
        probe_sha256=_SHA,
        snapshot=snapshot,
        command=CommandEvidence(
            argv=("docker", "run", "kicad"),
            started_utc="synthetic reachability fixture",
            returncode=0,
        ),
        command_path=Path("build/design-lint/reachability/native.command.json"),
        command_sha256=_SHA,
    )
    angle_map = PcbTrackAngleMap(
        basis="Synthetic independently reviewed route requirement",
        requirements=(
            PcbTrackAngleRequirement(
                id="clock-output",
                basis="Synthetic signal-integrity review",
                net="CLOCK_OUT",
                rule_name="clock-angle",
                minimum_degrees=150,
                maximum_degrees=None,
            ),
        ),
    )
    mapped_ids = {
        item.rule_id for item in track_angle_geometry_candidates(angle_map, evidence, _SHA)
    }
    acute_tracks = (
        first,
        second.model_copy(update={"end_nm": (0, 1_000_000)}),
    )
    acute_evidence = replace(
        evidence, snapshot=snapshot.model_copy(update={"tracks": acute_tracks})
    )
    acute_ids = {
        item.rule_id for item in unmapped_acute_track_corner_candidates(None, acute_evidence, _SHA)
    }
    return mapped_ids | acute_ids
