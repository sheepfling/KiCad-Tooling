"""Conservative centered-tip fit for supported native PCB pad apertures."""

from __future__ import annotations

import pytest

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
