"""Project-authored clearance checks against refilled outer copper zones."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.test_access import pcb_probe_envelope_checks
from tests.pcb_test_access_support import probe_access_requirement, probe_access_snapshot

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]

ZONE_UUID = "00000000-0000-0000-0000-000000000095"


@pytest.mark.parametrize(
    ("distance_nm", "expected_status"),
    [(500_000, "PASS"), (499_999, "FAIL")],
)
def test_authored_zone_clearance_uses_exact_native_boundary(
    distance_nm: int, expected_status: str
) -> None:
    requirement = probe_access_requirement(approach_side="front", zone_clearance_mm=0.1)
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="20",
        zone_obstacle_uuid=ZONE_UUID,
        zone_obstacle_layer="F.Cu",
        zone_obstacle_net="GND",
        zone_obstacle_island_index=0,
        zone_obstacle_distance_nm=distance_nm,
    )

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == expected_status
    assert ZONE_UUID in check.detail
    assert "island 0 on F.Cu" in check.detail
    assert "required envelope radius is 0.5 mm" in check.detail
    assert "regardless of solder-mask exposure" in check.detail


def test_authored_zone_clearance_supports_back_copper_evidence() -> None:
    requirement = probe_access_requirement(approach_side="back", zone_clearance_mm=0.1)
    snapshot = probe_access_snapshot(
        None,
        None,
        probe_side="back",
        include_back=False,
        schema_version="20",
        zone_obstacle_uuid=ZONE_UUID,
        zone_obstacle_layer="B.Cu",
        zone_obstacle_net="GND",
        zone_obstacle_island_index=0,
        zone_obstacle_distance_nm=500_000,
    )

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == "PASS"
    assert ZONE_UUID in check.detail
    assert "island 0 on B.Cu" in check.detail


def test_explicit_absence_of_foreign_zones_is_a_valid_control() -> None:
    requirement = probe_access_requirement(approach_side="front", zone_clearance_mm=0.1)
    snapshot = probe_access_snapshot(None, None, include_back=False, schema_version="20")

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == "PASS"
    assert "no different-net or unconnected filled outer-layer zone was observed" in check.detail


def test_zone_clearance_requires_schema_20_evidence() -> None:
    requirement = probe_access_requirement(approach_side="front", zone_clearance_mm=0.1)
    snapshot = probe_access_snapshot(None, None, include_back=False, schema_version="19")

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == "NOT_RUN"
    assert "schema v20 or newer" in check.detail


def test_zone_observation_must_reference_native_zone_and_island_inventory() -> None:
    with pytest.raises(ValidationError, match="unobserved zone"):
        probe_access_snapshot(
            None,
            None,
            include_back=False,
            schema_version="20",
            zone_obstacle_uuid=ZONE_UUID,
            zone_obstacle_layer="F.Cu",
            zone_obstacle_net="GND",
            zone_obstacle_island_index=0,
            zone_obstacle_distance_nm=500_000,
            include_zone_inventory=False,
        )

    with pytest.raises(ValidationError, match="unobserved zone island"):
        probe_access_snapshot(
            None,
            None,
            include_back=False,
            schema_version="20",
            zone_obstacle_uuid=ZONE_UUID,
            zone_obstacle_layer="F.Cu",
            zone_obstacle_net="GND",
            zone_obstacle_island_index=1,
            zone_obstacle_distance_nm=500_000,
        )


def test_zone_obstacle_net_and_outer_layer_must_match_inventory() -> None:
    with pytest.raises(ValidationError, match="zone net differs"):
        probe_access_snapshot(
            None,
            None,
            include_back=False,
            schema_version="20",
            zone_obstacle_uuid=ZONE_UUID,
            zone_obstacle_layer="F.Cu",
            zone_obstacle_net="WRONG_NET",
            zone_obstacle_island_index=0,
            zone_obstacle_distance_nm=500_000,
        )

    with pytest.raises(ValidationError, match="wrong outer layer"):
        probe_access_snapshot(
            None,
            None,
            include_back=False,
            schema_version="20",
            zone_obstacle_uuid=ZONE_UUID,
            zone_obstacle_layer="B.Cu",
            zone_obstacle_net="GND",
            zone_obstacle_island_index=0,
            zone_obstacle_distance_nm=500_000,
        )


def test_zone_evidence_is_rejected_before_schema_20() -> None:
    schema20_snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="20",
        zone_obstacle_uuid=ZONE_UUID,
        zone_obstacle_layer="F.Cu",
        zone_obstacle_net="GND",
        zone_obstacle_island_index=0,
        zone_obstacle_distance_nm=500_000,
    )

    with pytest.raises(ValidationError, match="requires schema v20"):
        PcbConnectivitySnapshot.model_validate(
            {**schema20_snapshot.model_dump(), "schema_version": "19"}
        )
