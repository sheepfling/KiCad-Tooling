"""Project-authored clearance checks against outer-layer PCB track copper."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.test_access import pcb_probe_envelope_checks
from tests.pcb_test_access_support import probe_access_requirement, probe_access_snapshot

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]

TRACK_UUID = "00000000-0000-0000-0000-000000000091"


@pytest.mark.parametrize(
    ("distance_nm", "expected_status"),
    [(500_000, "PASS"), (499_999, "FAIL")],
)
def test_authored_track_clearance_uses_exact_native_boundary(
    distance_nm: int, expected_status: str
) -> None:
    requirement = probe_access_requirement(approach_side="front", track_clearance_mm=0.1)
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="19",
        track_obstacle_uuid=TRACK_UUID,
        track_obstacle_net="GND",
        track_obstacle_distance_nm=distance_nm,
        track_obstacle_geometry="segment",
    )

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == expected_status
    assert TRACK_UUID in check.detail
    assert "segment" in check.detail
    assert "required envelope radius is 0.5 mm" in check.detail
    assert "regardless of solder-mask exposure" in check.detail


def test_unconnected_arc_is_reported_as_track_clearance_evidence() -> None:
    requirement = probe_access_requirement(approach_side="front", track_clearance_mm=0.1)
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="19",
        track_obstacle_uuid=TRACK_UUID,
        track_obstacle_net=None,
        track_obstacle_distance_nm=400_000,
        track_obstacle_geometry="arc",
    )

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == "FAIL"
    assert "arc" in check.detail
    assert "(no net)" in check.detail


def test_track_clearance_requires_schema_19_evidence() -> None:
    requirement = probe_access_requirement(approach_side="front", track_clearance_mm=0.1)
    snapshot = probe_access_snapshot(None, None, include_back=False, schema_version="18")

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == "NOT_RUN"
    assert "schema v19 or newer" in check.detail


def test_track_observation_must_reference_native_track_inventory() -> None:
    with pytest.raises(ValidationError, match="unobserved track"):
        probe_access_snapshot(
            None,
            None,
            include_back=False,
            schema_version="19",
            track_obstacle_uuid=TRACK_UUID,
            track_obstacle_net="GND",
            track_obstacle_distance_nm=500_000,
            track_obstacle_geometry="segment",
            include_track_inventory=False,
        )


def test_track_evidence_is_rejected_before_schema_19() -> None:
    schema19_snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="19",
        track_obstacle_uuid=TRACK_UUID,
        track_obstacle_net="GND",
        track_obstacle_distance_nm=500_000,
        track_obstacle_geometry="segment",
    )

    with pytest.raises(ValidationError, match="requires schema v19"):
        PcbConnectivitySnapshot.model_validate(
            {**schema19_snapshot.model_dump(), "schema_version": "18"}
        )
