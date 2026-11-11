"""Project-authored clearance to drilled openings on the requested PCB surface."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.test_access import (
    pcb_access_probe_request_set,
    pcb_probe_envelope_checks,
)
from tests.pcb_test_access_support import probe_access_requirement, probe_access_snapshot

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]

HOLE_ID = "pad:00000000-0000-0000-0000-000000000088"


@pytest.mark.parametrize(
    ("distance_nm", "expected_status"),
    ((500_000, "PASS"), (499_999, "FAIL")),
)
def test_authored_hole_clearance_uses_inclusive_nanometer_boundary(
    distance_nm: int, expected_status: str
) -> None:
    requirement = probe_access_requirement(
        approach_side="front",
        drill_hole_clearance_mm=0.1,
    )
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="22",
        hole_obstacle_id=HOLE_ID,
        hole_obstacle_distance_nm=distance_nm,
    )

    result = pcb_probe_envelope_checks(requirement, snapshot)[0]

    assert result.status == expected_status
    assert "nearest fitted drill hole" in result.detail


def test_hole_clearance_requests_hole_and_edge_source_inventory() -> None:
    requirement = probe_access_requirement(
        approach_side="front",
        drill_hole_clearance_mm=0.1,
    )

    request_set = pcb_access_probe_request_set(requirement)

    assert request_set is not None
    assert len(request_set.requests) == 1
    assert request_set.requests[0].include_drill_holes is True
    assert request_set.requests[0].include_edge_cuts is True


def test_hole_requirement_without_v22_evidence_is_not_run() -> None:
    requirement = probe_access_requirement(
        approach_side="front",
        drill_hole_clearance_mm=0.1,
    )
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="21",
    )

    result = pcb_probe_envelope_checks(requirement, snapshot)[0]

    assert result.id == "test-access/pcb-probe-envelope/drill-hole-evidence"
    assert result.status == "NOT_RUN"


def test_schema_v22_requires_explicit_hole_inventory_and_measurements() -> None:
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="22",
    )
    data = snapshot.model_dump()
    del data["drill_holes"]

    with pytest.raises(ValidationError, match="requires explicit drill-hole inventory"):
        PcbConnectivitySnapshot.model_validate(data)


def test_observation_must_reference_a_retained_drill_hole() -> None:
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="22",
        hole_obstacle_id=HOLE_ID,
        hole_obstacle_distance_nm=500_000,
    )
    data = snapshot.model_dump()
    data["access_probe_observations"][0]["hole_obstacle_id"] = "pad:unknown"

    with pytest.raises(ValidationError, match="refers to an unobserved drill hole"):
        PcbConnectivitySnapshot.model_validate(data)


def test_empty_surface_inventory_is_an_explicit_valid_control() -> None:
    requirement = probe_access_requirement(
        approach_side="front",
        drill_hole_clearance_mm=0.1,
    )
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="22",
    )

    result = pcb_probe_envelope_checks(requirement, snapshot)[0]

    assert result.status == "PASS"
    assert "no fitted surface drill hole was observed" in result.detail
