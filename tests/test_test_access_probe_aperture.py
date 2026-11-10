"""Conservative centered-tip fit for supported native PCB pad apertures."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.pcb_connectivity_observations import PcbAccessProbeObservation
from kicad_tooling.hwrepo.test_access import pcb_probe_envelope_checks
from tests.pcb_test_access_support import probe_access_requirement, probe_access_snapshot

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


@pytest.mark.parametrize(
    "shape",
    ["circle", "oval", "rectangle", "roundrect"],
)
def test_supported_pad_shapes_accept_exact_centered_tip_boundary(shape: str) -> None:
    requirement = probe_access_requirement(approach_side="front")
    snapshot = probe_access_snapshot(
        500_000,
        None,
        include_back=False,
        aperture_shape=shape,
        aperture_diameter_nm=1_000_000,
    )

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == "PASS"
    assert "required tip-plus-clearance diameter is 1 mm" in check.detail


@pytest.mark.parametrize("shape", ["oval", "rectangle", "roundrect"])
def test_supported_pad_shapes_reject_one_nanometer_below_tip_boundary(shape: str) -> None:
    requirement = probe_access_requirement(approach_side="front")
    snapshot = probe_access_snapshot(
        500_000,
        None,
        include_back=False,
        aperture_shape=shape,
        aperture_diameter_nm=999_999,
    )

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == "FAIL"
    assert "0.999999 mm" in check.detail


def test_unsupported_aperture_shape_stays_unproven() -> None:
    requirement = probe_access_requirement(approach_side="front")
    snapshot = probe_access_snapshot(
        500_000,
        None,
        include_back=False,
        aperture_shape="unsupported",
        aperture_diameter_nm=None,
    )

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == "FAIL"
    assert "shape is unsupported" in check.detail


@pytest.mark.parametrize("shape", ["circle", "oval", "rectangle", "roundrect"])
def test_supported_native_shape_requires_a_fit_measurement(shape: str) -> None:
    with pytest.raises(ValueError, match="positive fit diameter"):
        PcbAccessProbeObservation(
            endpoint="J1.9",
            side="front",
            target_net="RESET_N",
            target_exposed=True,
            obstacle=None,
            obstacle_net=None,
            distance_nm=None,
            target_aperture_shape=shape,
            target_aperture_diameter_nm=None,
        )


@pytest.mark.parametrize(
    ("distance_nm", "expected_status"),
    [(500_000, "PASS"), (499_999, "FAIL")],
)
def test_authored_courtyard_clearance_uses_exact_native_boundary(
    distance_nm: int, expected_status: str
) -> None:
    requirement = probe_access_requirement(approach_side="front", courtyard_clearance_mm=0.1)
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="17",
        courtyard_obstacle="U1",
        courtyard_distance_nm=distance_nm,
    )

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == expected_status
    assert "required probe radius plus courtyard clearance is 0.5 mm" in check.detail


def test_nearby_footprint_without_courtyard_stays_unresolved() -> None:
    requirement = probe_access_requirement(approach_side="front", courtyard_clearance_mm=0.1)
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="17",
        unmeasured_courtyard_footprint="U1",
        unmeasured_courtyard_distance_nm=500_000,
    )

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == "NOT_RUN"
    assert "U1 has no same-side courtyard" in check.detail


def test_authored_courtyard_clearance_requires_current_native_evidence() -> None:
    requirement = probe_access_requirement(approach_side="front", courtyard_clearance_mm=0.1)
    snapshot = probe_access_snapshot(None, None, include_back=False)

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == "NOT_RUN"
    assert "schema v17 or newer" in check.detail


@pytest.mark.parametrize(
    ("distance_nm", "expected_status"),
    [(500_000, "PASS"), (499_999, "FAIL")],
)
def test_authored_untented_via_clearance_uses_exact_native_boundary(
    distance_nm: int, expected_status: str
) -> None:
    requirement = probe_access_requirement(approach_side="front", via_clearance_mm=0.1)
    snapshot = probe_access_snapshot(
        None,
        None,
        include_back=False,
        schema_version="18",
        via_obstacle_id="e" * 64,
        via_obstacle_net="GND",
        via_obstacle_distance_nm=distance_nm,
        via_obstacle_tented=False,
    )

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == expected_status
    assert "untented via" in check.detail
    assert "required envelope radius is 0.5 mm" in check.detail


def test_authored_via_clearance_requires_current_native_evidence() -> None:
    requirement = probe_access_requirement(approach_side="front", via_clearance_mm=0.1)
    snapshot = probe_access_snapshot(None, None, include_back=False)

    (check,) = pcb_probe_envelope_checks(requirement, snapshot)

    assert check.status == "NOT_RUN"
    assert "schema v18 or newer" in check.detail


def test_via_access_observation_must_reference_observed_untented_via() -> None:
    with pytest.raises(ValidationError, match="unobserved via"):
        probe_access_snapshot(
            None,
            None,
            include_back=False,
            schema_version="18",
            via_obstacle_id="f" * 64,
            via_obstacle_net="GND",
            via_obstacle_distance_nm=500_000,
            via_obstacle_tented=False,
            include_via_inventory=False,
        )


def test_courtyard_measurement_must_reference_observed_same_side_footprint() -> None:
    with pytest.raises(ValidationError, match="unobserved footprint"):
        probe_access_snapshot(
            None,
            None,
            include_back=False,
            schema_version="17",
            courtyard_obstacle="U9",
            courtyard_distance_nm=500_000,
        )
