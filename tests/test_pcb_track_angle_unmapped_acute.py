"""Opt-in review of acute routed corners omitted from authored angle maps."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_pcb_coverage_common import PcbGeometrySourceEvidence
from kicad_tooling.hwrepo.design_lint_pcb_track_angle_geometry_scan import (
    track_angle_geometry_candidates_for_scan,
    track_angle_geometry_scan_required,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.pcb_connectivity_observations import PcbTrackObservation
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_track_angle_geometry import RULE_ID as MAPPED_RULE_ID
from kicad_tooling.hwrepo.pcb_track_angle_models import (
    PcbTrackAngleMap,
    PcbTrackAngleRequirement,
)
from kicad_tooling.hwrepo.pcb_track_angle_unmapped_geometry import (
    RULE_ID,
    unmapped_acute_track_corner_candidates,
)
from kicad_tooling.hwrepo.project_models import (
    ComponentIdentity,
    IgnoredChecks,
    ProjectConfig,
    ProjectKind,
    ProjectTestContract,
    SchematicValidationContract,
)
from tests.json_types import JsonObject

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]

_SHA = "a" * 64
_TRACK_A = "00000000-0000-0000-0000-000000000001"
_TRACK_B = "00000000-0000-0000-0000-000000000002"


def _track(
    uuid: str,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    net: str = "DATA",
    start_tracks: tuple[str, ...] = (),
    end_tracks: tuple[str, ...] = (),
    kind: str = "segment",
) -> PcbTrackObservation:
    return PcbTrackObservation(
        uuid=uuid,
        net=net,
        layer="F.Cu",
        width_nm=250_000,
        start_nm=start,
        end_nm=end,
        geometry_kind=kind,  # type: ignore[arg-type]
        start_pads=(),
        end_pads=(),
        start_vias=(),
        end_vias=(),
        start_tracks=start_tracks,
        end_tracks=end_tracks,
    )


def _snapshot(
    second_end: tuple[int, int] = (0, 1_000_000),
    *,
    net: str = "DATA",
    second_kind: str = "segment",
    version: str = "10.0.5",
) -> PcbConnectivitySnapshot:
    first = _track(
        _TRACK_A,
        (0, 0),
        (1_000_000, 0),
        net=net,
        end_tracks=(_TRACK_B,),
    )
    second = _track(
        _TRACK_B,
        (1_000_000, 0),
        second_end,
        net=net,
        start_tracks=(_TRACK_A,),
        kind=second_kind,
    )
    return PcbConnectivitySnapshot(
        schema_version="8",
        board_sha256=_SHA,
        kicad_version=version,
        image=f"ghcr.io/kicad/kicad:{version}@sha256:{_SHA}",
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


def _evidence(snapshot: PcbConnectivitySnapshot, root: Path) -> PcbGeometrySourceEvidence:
    return PcbGeometrySourceEvidence(
        board_path="projects/controller/kicad/controller.kicad_pcb",
        board_sha256=_SHA,
        snapshot_relative_path="build/design-lint/acute-corner/snapshot.json",
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


def _angle_map(net: str = "DATA") -> PcbTrackAngleMap:
    return PcbTrackAngleMap(
        basis="Synthetic independently reviewed track-angle scope",
        requirements=(
            PcbTrackAngleRequirement(
                id="data-angle",
                basis="Synthetic route review",
                net=net,
                rule_name="data-track-angle",
                minimum_degrees=90,
            ),
        ),
    )


def _enabled_policy(mode: str = "review") -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,  # type: ignore[arg-type]
                reason="Review acute corners outside authored map scope",
            ),
        )
    )


def test_unmapped_acute_corner_is_source_bound_and_names_track_geometry(tmp_path: Path) -> None:
    (candidate,) = unmapped_acute_track_corner_candidates(
        None,
        _evidence(_snapshot(), tmp_path),
        _SHA,
    )

    assert candidate.rule_id == RULE_ID
    assert candidate.subject == "DATA F.Cu corner at 1000000,0 nm"
    assert candidate.evidence["measured_angle_degrees"] == ("45.000",)
    assert candidate.evidence["track_uuids"] == (_TRACK_A, _TRACK_B)
    assert candidate.evidence["board_sha256"] == (_SHA,)
    assert candidate.evidence["snapshot_sha256"] == (_SHA,)
    assert candidate.evidence["probe_sha256"] == (_SHA,)
    assert candidate.evidence["netlist_sha256"] == (_SHA,)
    assert candidate.evidence["angle_map_sha256"] == ("<absent>",)


@pytest.mark.parametrize(
    ("second_end", "expected_angle"),
    [
        ((2_000_000, 1_000_000), None),  # ordinary 45-degree route, 135-degree interior
        ((1_000_000, 1_000_000), None),  # right angle
        ((982_545, 1_000_000), None),  # rounds to the exclusive 89.000-degree threshold
        ((982_500, 1_000_000), "88.997"),  # below threshold after deterministic rounding
    ],
    ids=("ordinary-45-degree-route", "right-angle", "89-degree-boundary", "acute-below-boundary"),
)
def test_threshold_is_exclusive_and_uses_millidegree_measurement(
    tmp_path: Path,
    second_end: tuple[int, int],
    expected_angle: str | None,
) -> None:
    candidates = unmapped_acute_track_corner_candidates(
        None,
        _evidence(_snapshot(second_end), tmp_path),
        _SHA,
    )

    if expected_angle is None:
        assert candidates == ()
    else:
        assert len(candidates) == 1
        assert candidates[0].evidence["measured_angle_degrees"] == (expected_angle,)


def test_authored_angle_map_suppresses_unmapped_scope_prompt(tmp_path: Path) -> None:
    evidence = _evidence(_snapshot(), tmp_path)

    assert unmapped_acute_track_corner_candidates(_angle_map(), evidence, _SHA) == ()
    mapped_candidates = unmapped_acute_track_corner_candidates(_angle_map("OTHER"), evidence, _SHA)
    assert len(mapped_candidates) == 1


def test_arc_and_nonreciprocal_contacts_are_not_measured(tmp_path: Path) -> None:
    arc = _evidence(_snapshot(second_kind="arc"), tmp_path)
    assert unmapped_acute_track_corner_candidates(None, arc, _SHA) == ()

    first = _track(_TRACK_A, (0, 0), (1_000_000, 0), end_tracks=(_TRACK_B,))
    second = _track(_TRACK_B, (1_000_000, 0), (0, 1_000_000))
    snapshot = _snapshot().model_copy(update={"tracks": (first, second)})
    assert unmapped_acute_track_corner_candidates(None, _evidence(snapshot, tmp_path), _SHA) == ()


def test_review_is_opt_in_and_missing_or_unsupported_evidence_is_incomplete() -> None:
    config = ProjectConfig.model_construct(
        kind=ProjectKind.PCB,
        project="projects/controller/kicad/controller.kicad_pro",
        kicad_version="10.0.5",
        image=f"ghcr.io/kicad/kicad:10.0.5@sha256:{_SHA}",
    )
    hashes: JsonObject = {"projects/controller/kicad/controller.kicad_pcb": _SHA}
    disabled = DesignLintPolicy()
    enabled = _enabled_policy()

    assert not track_angle_geometry_scan_required(config, disabled)
    assert track_angle_geometry_scan_required(config, enabled)
    assert track_angle_geometry_candidates_for_scan(config, disabled, hashes) == ()
    (missing,) = track_angle_geometry_candidates_for_scan(config, enabled, hashes)
    assert missing.rule_id == RULE_ID
    assert missing.evidence["coverage_status"] == ("INCOMPLETE",)

    (unsupported,) = unmapped_acute_track_corner_candidates(
        None,
        _evidence(_snapshot(version="10.0.8"), Path(".")),
        _SHA,
    )
    assert unsupported.evidence["coverage_status"] == ("INCOMPLETE",)
    assert "only been validated" in unsupported.message


def test_metamorphic_translation_and_snapshot_order_preserve_angle(tmp_path: Path) -> None:
    original = _evidence(_snapshot(), tmp_path)
    tracks = tuple(
        track.model_copy(
            update={
                "start_nm": (track.start_nm[0] + 7_000_000, track.start_nm[1] - 4_000_000),
                "end_nm": (track.end_nm[0] + 7_000_000, track.end_nm[1] - 4_000_000),
            }
        )
        for track in reversed(original.snapshot.tracks)
    )
    translated = original.snapshot.model_copy(update={"tracks": tracks})

    (baseline,) = unmapped_acute_track_corner_candidates(None, original, _SHA)
    (changed,) = unmapped_acute_track_corner_candidates(None, _evidence(translated, tmp_path), _SHA)

    assert baseline.evidence["measured_angle_degrees"] == changed.evidence["measured_angle_degrees"]


def test_rule_override_can_be_promoted_or_disabled_per_project() -> None:
    config = ProjectConfig.model_construct(
        kind=ProjectKind.PCB,
        project="projects/controller/kicad/controller.kicad_pro",
        kicad_version="10.0.5",
        image=f"ghcr.io/kicad/kicad:10.0.5@sha256:{_SHA}",
    )
    hashes: JsonObject = {"projects/controller/kicad/controller.kicad_pcb": _SHA}
    disabled = _enabled_policy("off")
    blocking = _enabled_policy("block")

    assert not track_angle_geometry_scan_required(config, disabled)
    assert track_angle_geometry_scan_required(config, blocking)
    (candidate,) = track_angle_geometry_candidates_for_scan(config, blocking, hashes)
    assert candidate.rule_id == RULE_ID
    assert MAPPED_RULE_ID == "pcb.track_angle_geometry_review"


def test_acute_corner_override_requires_a_pcb_project() -> None:
    policy = _enabled_policy()
    schematic = SchematicValidationContract(
        kind=ProjectKind.SCHEMATIC,
        expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
    )

    with pytest.raises(
        ValidationError, match="PCB geometry maps require an authoritative PCB project"
    ):
        ProjectConfig(
            schema_version="1",
            kind=ProjectKind.SCHEMATIC,
            assurance_profile="development",
            not_for_manufacture=True,
            project_id="synthetic-schematic",
            component_identity=ComponentIdentity(required=False, part_ids=()),
            toolchain_id="synthetic-kicad-10",
            kicad_version="10.0.5",
            image=f"ghcr.io/kicad/kicad:10.0.5@sha256:{_SHA}",
            project="projects/synthetic/synthetic.kicad_pro",
            source_roots=("projects/synthetic",),
            required_inputs=(),
            validation=schematic,
            design_lint=policy,
        )

    with pytest.raises(
        ValidationError, match="PCB geometry maps require an authoritative PCB project"
    ):
        ProjectTestContract(validation=schematic, design_lint=policy)
