"""Synthetic via-probe fixtures and native observation assertions."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from .hwrepo.pcb_connectivity_observations import PcbAccessProbeObservation
from .hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .hwrepo.pcb_test_access_models import RequiredTestAccess, TestAccessEndpointRequirement

VIA_PROBE_EXPECTED_STATUSES = {
    "test-access/pcb-probe-envelope/untented-via-clearance-fault": "FAIL",
    "test-access/pcb-probe-envelope/untented-via-clearance-boundary-control": "PASS",
    "test-access/pcb-probe-envelope/tented-via-control": "PASS",
    "test-access/pcb-probe-envelope/back-untented-via-clearance-fault": "FAIL",
}

VIA_PROBE_EXPECTED_PAD_OBSERVATIONS = {
    ("j20.1", "front"): (
        "J19.1",
        "TARGET_COURTYARD_SMALL",
        9_500_001,
        True,
        "circle",
        800_000,
    ),
    ("j21.1", "front"): (
        "J20.1",
        "TARGET_VIA_FAULT",
        9_750_001,
        True,
        "circle",
        800_000,
    ),
    ("j22.1", "front"): (
        "J21.1",
        "TARGET_VIA_BOUNDARY",
        9_750_001,
        True,
        "circle",
        800_000,
    ),
    ("j23.1", "back"): (
        "J14.1",
        "TARGET_APERTURE_DRILLED",
        89_500_001,
        True,
        "circle",
        800_000,
    ),
}

_VIA_EXPECTED = {
    ("j20.1", "front"): ("FOREIGN_VIA", 400_000, False),
    ("j21.1", "front"): ("FOREIGN_VIA", 400_000, False),
    # The nearby tented via is excluded; the recorded nearest open via is 9 mm away.
    ("j22.1", "front"): ("FOREIGN_VIA", 9_000_002, False),
    ("j23.1", "back"): ("FOREIGN_VIA_BACK", 400_001, False),
}


def via_probe_fixture_decisions(
    endpoint: Callable[..., TestAccessEndpointRequirement],
) -> tuple[RequiredTestAccess, ...]:
    """Build project-authored via-clearance fault and control requirements."""
    return (
        RequiredTestAccess(
            mode="required",
            id="untented-via-clearance-fault",
            basis="Synthetic untented via lies one nanometer inside the authored envelope",
            net="TARGET_VIA_FAULT",
            endpoints=(
                endpoint(
                    "J20",
                    "TARGET_VIA_FAULT",
                    approach_side="front",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    via_clearance_mm=0.100001,
                ),
            ),
        ),
        RequiredTestAccess(
            mode="required",
            id="untented-via-clearance-boundary-control",
            basis="Synthetic foreign untented via sits at the exact authored clearance boundary",
            net="TARGET_VIA_BOUNDARY",
            endpoints=(
                endpoint(
                    "J21",
                    "TARGET_VIA_BOUNDARY",
                    approach_side="front",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    via_clearance_mm=0.1,
                ),
            ),
        ),
        RequiredTestAccess(
            mode="required",
            id="tented-via-control",
            basis="Synthetic nearby foreign via is tented on the requested outer side",
            net="TARGET_TENTED_VIA",
            endpoints=(
                endpoint(
                    "J22",
                    "TARGET_TENTED_VIA",
                    approach_side="front",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    via_clearance_mm=0.1,
                ),
            ),
        ),
        RequiredTestAccess(
            mode="required",
            id="back-untented-via-clearance-fault",
            basis="Synthetic back-side untented via lies one nanometer inside the authored envelope",
            net="TARGET_BACK_VIA",
            endpoints=(
                endpoint(
                    "J23",
                    "TARGET_BACK_VIA",
                    approach_side="back",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    via_clearance_mm=0.100002,
                ),
            ),
        ),
    )


def validate_via_probe_fixture_observations(
    snapshot: PcbConnectivitySnapshot,
    observations: Mapping[tuple[str, str], PcbAccessProbeObservation],
) -> None:
    """Require the exact expected via identity, side, net, and native distance."""
    vias_by_id = {via.id: via for via in snapshot.vias}
    for key, expected in _VIA_EXPECTED.items():
        item = observations[key]
        via = vias_by_id.get(item.via_obstacle_id) if item.via_obstacle_id else None
        observed = (
            None if via is None else via.net,
            item.via_obstacle_distance_nm,
            item.via_obstacle_tented,
        )
        if observed != expected:
            raise ValueError(
                f"Native via geometry for {key[0]} {key[1]} differs from its fixture: "
                f"expected {expected}, found {observed}"
            )
