"""Deterministic corner-angle review over source-bound native PCB observations."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_pcb_coverage_common import PcbGeometrySourceEvidence
from kicad_tooling.hwrepo.design_lint_pcb_track_angle_geometry_scan import (
    track_angle_geometry_candidates_for_scan,
    track_angle_geometry_scan_required,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.pcb_connectivity_observations import (
    PcbPadConnectivityObservation,
    PcbTrackObservation,
    PcbViaObservation,
)
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_track_angle_geometry import (
    RULE_ID,
    track_angle_geometry_candidates,
    track_angle_geometry_map_missing_candidate,
    track_angle_geometry_unavailable_candidate,
    track_angle_geometry_violations,
)
from kicad_tooling.hwrepo.pcb_track_angle_models import (
    PcbTrackAngleMap,
    PcbTrackAngleRequirement,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind
from tests.json_types import JsonObject

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]

_SHA = "0" * 64
_TRACK_A = "00000000-0000-0000-0000-000000000001"
_TRACK_B = "00000000-0000-0000-0000-000000000002"
_TRACK_C = "00000000-0000-0000-0000-000000000003"
_VIA = "1" * 64


def _track(
    uuid: str,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    start_tracks: tuple[str, ...] = (),
    end_tracks: tuple[str, ...] = (),
    start_pads: tuple[str, ...] = (),
    end_pads: tuple[str, ...] = (),
    start_vias: tuple[str, ...] = (),
    end_vias: tuple[str, ...] = (),
    kind: str = "segment",
) -> PcbTrackObservation:
    return PcbTrackObservation(
        uuid=uuid,
        net="CLOCK_OUT",
        layer="F.Cu",
        width_nm=250_000,
        start_nm=start,
        end_nm=end,
        geometry_kind=kind,  # type: ignore[arg-type]
        start_pads=start_pads,
        end_pads=end_pads,
        start_vias=start_vias,
        end_vias=end_vias,
        start_tracks=start_tracks,
        end_tracks=end_tracks,
    )


def _snapshot(
    tracks: tuple[PcbTrackObservation, ...],
    *,
    pads: tuple[PcbPadConnectivityObservation, ...] = (),
    vias: tuple[PcbViaObservation, ...] = (),
    version: str = "10.0.5",
) -> PcbConnectivitySnapshot:
    return PcbConnectivitySnapshot(
        schema_version="8",
        board_sha256=_SHA,
        kicad_version=version,
        image="ghcr.io/kicad/kicad:10.0.5@sha256:" + _SHA,
        probe_sha256=_SHA,
        zones_refilled=True,
        pads=pads,
        net_ties=(),
        zones=(),
        vias=vias,
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=tracks,
        copper_layers=("F.Cu", "B.Cu"),
    )


def _angle_map(*, minimum: int | None = 150, maximum: int | None = None) -> PcbTrackAngleMap:
    return PcbTrackAngleMap(
        basis="Synthetic, explicitly reviewed track-angle requirement",
        requirements=(
            PcbTrackAngleRequirement(
                id="clock-output",
                basis="Synthetic signal-integrity review",
                net="CLOCK_OUT",
                rule_name="clock-angle",
                minimum_degrees=minimum,
                maximum_degrees=maximum,
            ),
        ),
    )


def _corner_tracks(
    second_end: tuple[int, int] = (2_000_000, 1_000_000),
    *,
    kind: str = "segment",
) -> tuple[PcbTrackObservation, PcbTrackObservation]:
    return (
        _track(_TRACK_A, (0, 0), (1_000_000, 0), end_tracks=(_TRACK_B,)),
        _track(
            _TRACK_B,
            (1_000_000, 0),
            second_end,
            start_tracks=(_TRACK_A,),
            kind=kind,
        ),
    )


def _source_evidence(snapshot: PcbConnectivitySnapshot, root: Path) -> PcbGeometrySourceEvidence:
    return PcbGeometrySourceEvidence(
        board_path="projects/controller/kicad/controller.kicad_pcb",
        board_sha256=_SHA,
        snapshot_relative_path="build/design-lint/pcb-geometry-test/snapshot.json",
        snapshot_path=root / "snapshot.json",
        snapshot_sha256=_SHA,
        probe_sha256=_SHA,
        snapshot=snapshot,
        command=CommandEvidence(
            argv=("docker", "run", "kicad"),
            started_utc="synthetic source-bound fixture",
            returncode=0,
        ),
        command_path=root / "native.command.json",
        command_sha256=_SHA,
    )


def test_authored_minimum_detects_135_degree_corner_and_accepts_collinear_control() -> None:
    fault = _snapshot(_corner_tracks())
    control = _snapshot(_corner_tracks((2_000_000, 0)))

    violations = track_angle_geometry_violations(_angle_map(), fault)

    assert len(violations) == 1
    assert violations[0].angle_millidegrees == 135_000
    assert violations[0].bound_issue == "below the configured 150 degree minimum"
    assert track_angle_geometry_violations(_angle_map(), control) == ()


@pytest.mark.parametrize(
    ("end", "minimum", "expected_millidegrees"),
    [
        ((0, 1_000_000), 90, 45_000),
        ((2_000_000, 1_000_000), 135, 135_000),
        ((2_732_051, 1_000_000), 150, 150_000),
    ],
    ids=("acute", "right-angle-boundary", "authored-minimum-boundary"),
)
def test_integer_geometry_measurement_is_stable_at_authored_boundaries(
    end: tuple[int, int], minimum: int, expected_millidegrees: int
) -> None:
    tracks = _corner_tracks(end)
    snapshot = _snapshot(tracks)

    violations = track_angle_geometry_violations(_angle_map(minimum=minimum), snapshot)

    if expected_millidegrees < minimum * 1000:
        assert len(violations) == 1
        assert violations[0].angle_millidegrees == expected_millidegrees
    else:
        assert violations == ()


def test_metamorphic_translation_rotation_and_snapshot_order_preserve_angle() -> None:
    angle_map = _angle_map()

    def signature(tracks: tuple[PcbTrackObservation, ...]) -> tuple[tuple[object, ...], ...]:
        return tuple(
            (
                item.requirement.net,
                item.first_track_uuid,
                item.second_track_uuid,
                item.angle_millidegrees,
                item.bound_issue,
            )
            for item in track_angle_geometry_violations(angle_map, _snapshot(tracks))
        )

    original = _corner_tracks()
    translated = tuple(
        track.model_copy(
            update={
                "start_nm": (track.start_nm[0] + 5_000_000, track.start_nm[1] - 3_000_000),
                "end_nm": (track.end_nm[0] + 5_000_000, track.end_nm[1] - 3_000_000),
            }
        )
        for track in original
    )
    rotated = tuple(
        track.model_copy(
            update={
                "start_nm": (-track.start_nm[1], track.start_nm[0]),
                "end_nm": (-track.end_nm[1], track.end_nm[0]),
            }
        )
        for track in reversed(original)
    )

    expected = signature(original)
    assert expected == (
        ("CLOCK_OUT", _TRACK_A, _TRACK_B, 135_000, "below the configured 150 degree minimum"),
    )
    assert signature(translated) == expected
    assert signature(rotated) == expected


def test_maximum_bound_flags_straight_continuation() -> None:
    snapshot = _snapshot(_corner_tracks((2_000_000, 0)))

    violations = track_angle_geometry_violations(_angle_map(minimum=None, maximum=170), snapshot)

    assert len(violations) == 1
    assert violations[0].angle_millidegrees == 180_000
    assert violations[0].bound_issue == "above the configured 170 degree maximum"


@pytest.mark.parametrize("kind", ["arc"], ids=("arc-contact",))
def test_arc_contacts_are_skipped(kind: str) -> None:
    snapshot = _snapshot(_corner_tracks(kind=kind))

    assert track_angle_geometry_violations(_angle_map(), snapshot) == ()


def test_branch_pad_and_via_vertices_are_skipped() -> None:
    branch = (
        _track(
            _TRACK_A,
            (0, 0),
            (1_000_000, 0),
            end_tracks=(_TRACK_B, _TRACK_C),
        ),
        _track(
            _TRACK_B,
            (1_000_000, 0),
            (2_000_000, 1_000_000),
            start_tracks=(_TRACK_A, _TRACK_C),
        ),
        _track(
            _TRACK_C,
            (1_000_000, 0),
            (2_000_000, -1_000_000),
            start_tracks=(_TRACK_A, _TRACK_B),
        ),
    )
    assert track_angle_geometry_violations(_angle_map(), _snapshot(branch)) == ()

    pad = PcbPadConnectivityObservation(
        pad="J1.1",
        net="CLOCK_OUT",
        footprint="Connector_Generic:Conn_01x01",
        dnp=False,
        connected_pads=("J1.1",),
        connected_zones=(),
        connected_islands=(),
        connected_vias=(),
        positions_nm=((1_000_000, 0),),
    )
    pad_tracks = (
        _track(_TRACK_A, (0, 0), (1_000_000, 0), end_tracks=(_TRACK_B,), end_pads=("J1.1",)),
        _track(
            _TRACK_B,
            (1_000_000, 0),
            (2_000_000, 1_000_000),
            start_tracks=(_TRACK_A,),
            start_pads=("J1.1",),
        ),
    )
    assert track_angle_geometry_violations(_angle_map(), _snapshot(pad_tracks, pads=(pad,))) == ()

    via = PcbViaObservation(
        id=_VIA,
        net="CLOCK_OUT",
        x_nm=1_000_000,
        y_nm=0,
        start_layer="F.Cu",
        end_layer="B.Cu",
        diameter_nm=600_000,
        drill_nm=300_000,
        kind="through",
        multiplicity=1,
    )
    via_tracks = (
        _track(_TRACK_A, (0, 0), (1_000_000, 0), end_tracks=(_TRACK_B,), end_vias=(_VIA,)),
        _track(
            _TRACK_B,
            (1_000_000, 0),
            (2_000_000, 1_000_000),
            start_tracks=(_TRACK_A,),
            start_vias=(_VIA,),
        ),
    )
    assert track_angle_geometry_violations(_angle_map(), _snapshot(via_tracks, vias=(via,))) == ()


def test_nonreciprocal_native_contacts_are_skipped() -> None:
    tracks = (
        _track(_TRACK_A, (0, 0), (1_000_000, 0), end_tracks=(_TRACK_B,)),
        _track(_TRACK_B, (1_000_000, 0), (2_000_000, 1_000_000)),
    )

    assert track_angle_geometry_violations(_angle_map(), _snapshot(tracks)) == ()


def test_candidate_carries_board_map_probe_and_track_identity(tmp_path: Path) -> None:
    snapshot = _snapshot(_corner_tracks())
    evidence = _source_evidence(snapshot, tmp_path)

    candidates = track_angle_geometry_candidates(_angle_map(), evidence, _SHA)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.rule_id == RULE_ID
    assert (
        candidate.message
        == "Measured 135.000 degree corner is below the configured 150 degree minimum."
    )
    assert candidate.evidence["track_uuids"] == (_TRACK_A, _TRACK_B)
    assert candidate.evidence["board_sha256"] == (_SHA,)
    assert candidate.evidence["snapshot_sha256"] == (_SHA,)
    assert candidate.evidence["probe_sha256"] == (_SHA,)
    assert candidate.evidence["netlist_sha256"] == (_SHA,)


def test_unsupported_kicad_version_stays_incomplete(tmp_path: Path) -> None:
    snapshot = _snapshot(_corner_tracks(), version="10.0.8")
    evidence = _source_evidence(snapshot, tmp_path)

    candidate = track_angle_geometry_candidates(_angle_map(), evidence, _SHA)[0]

    assert candidate.evidence["coverage_status"] == ("INCOMPLETE",)
    assert "only been validated" in candidate.message


def test_capture_failure_and_missing_map_are_explicit_candidates() -> None:
    config = ProjectConfig.model_construct(
        project="projects/controller/kicad/controller.kicad_pro",
        kicad_version="10.0.5",
        image="ghcr.io/kicad/kicad:10.0.5@sha256:" + _SHA,
    )
    hashes: JsonObject = {
        "projects/controller/kicad/controller.kicad_pcb": _SHA,
        "projects/controller/kicad/controller.kicad_pro": _SHA,
    }
    policy = DesignLintPolicy(pcb_track_angle_map=_angle_map())

    unavailable = track_angle_geometry_unavailable_candidate(
        config, policy, hashes, "synthetic probe failure"
    )
    missing = track_angle_geometry_map_missing_candidate(config, hashes)

    assert unavailable is not None
    assert unavailable.evidence["coverage_status"] == ("INCOMPLETE",)
    assert "synthetic probe failure" in unavailable.message
    assert missing.rule_id == RULE_ID
    assert "no pcb_track_angle_map" in missing.message


def test_geometry_review_is_opt_in_and_requires_authored_scope() -> None:
    config = ProjectConfig.model_construct(
        kind=ProjectKind.PCB,
        project="projects/controller/kicad/controller.kicad_pro",
        kicad_version="10.0.5",
        image="ghcr.io/kicad/kicad:10.0.5@sha256:" + _SHA,
    )
    hashes: JsonObject = {
        "projects/controller/kicad/controller.kicad_pro": _SHA,
    }
    disabled = DesignLintPolicy(pcb_track_angle_map=_angle_map())
    enabled_without_map = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Exercise explicit opt-in without a requirements map",
            ),
        )
    )
    enabled = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Cross-check approved route-angle requirements",
            ),
        ),
        pcb_track_angle_map=_angle_map(),
    )

    assert not track_angle_geometry_scan_required(config, disabled)
    assert not track_angle_geometry_scan_required(config, enabled_without_map)
    assert not track_angle_geometry_candidates_for_scan(config, disabled, hashes)
    assert track_angle_geometry_candidates_for_scan(config, enabled_without_map, hashes)
    assert track_angle_geometry_scan_required(config, enabled)
