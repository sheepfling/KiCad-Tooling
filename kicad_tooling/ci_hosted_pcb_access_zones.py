"""Synthetic filled-zone clearance scenarios for native probe acceptance."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from .hwrepo.pcb_connectivity_observations import PcbAccessProbeObservation
from .hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .hwrepo.pcb_test_access_models import RequiredTestAccess, TestAccessEndpointRequirement

ZONE_PROBE_EXPECTED_STATUSES = {
    "test-access/pcb-probe-envelope/zone-clearance-fault": "FAIL",
    "test-access/pcb-probe-envelope/zone-clearance-boundary-control": "PASS",
    "test-access/pcb-probe-envelope/same-net-zone-control": "PASS",
    "test-access/pcb-probe-envelope/filled-zone-hole-control": "PASS",
    "test-access/pcb-probe-envelope/back-zone-clearance-fault": "FAIL",
    "test-access/pcb-probe-envelope/back-zone-clearance-boundary-control": "PASS",
}

ZONE_PROBE_EXPECTED_OBSERVATIONS = {
    ("j28.1", "front"): (
        "00000000-0000-0000-0000-000000000050",
        "F.Cu",
        "FOREIGN_ZONE_FAULT",
        0,
        450_499,
    ),
    ("j29.1", "front"): (
        "00000000-0000-0000-0000-000000000051",
        "F.Cu",
        "FOREIGN_ZONE_BOUNDARY",
        0,
        450_499,
    ),
    ("j30.1", "front"): (
        "00000000-0000-0000-0000-000000000051",
        "F.Cu",
        "FOREIGN_ZONE_BOUNDARY",
        0,
        9_000_000,
    ),
    ("j31.1", "front"): (
        "00000000-0000-0000-0000-000000000053",
        "F.Cu",
        "FOREIGN_ZONE_HOLE",
        0,
        450_499,
    ),
    ("j32.1", "back"): (
        "00000000-0000-0000-0000-000000000054",
        "B.Cu",
        "FOREIGN_ZONE_BACK_FAULT",
        0,
        450_499,
    ),
    ("j33.1", "back"): (
        "00000000-0000-0000-0000-000000000055",
        "B.Cu",
        "FOREIGN_ZONE_BACK_BOUNDARY",
        0,
        450_499,
    ),
}


def zone_probe_fixture_decisions(
    endpoint: Callable[..., TestAccessEndpointRequirement],
) -> tuple[RequiredTestAccess, ...]:
    """Build authored fault and control requirements for filled-zone clearance."""
    return (
        RequiredTestAccess(
            mode="required",
            id="zone-clearance-fault",
            basis="Synthetic foreign filled zone lies one nanometer inside the authored envelope",
            net="TARGET_ZONE_FAULT",
            endpoints=(
                endpoint(
                    "J28",
                    "TARGET_ZONE_FAULT",
                    approach_side="front",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    zone_clearance_mm=0.1505,
                ),
            ),
        ),
        RequiredTestAccess(
            mode="required",
            id="zone-clearance-boundary-control",
            basis="Synthetic foreign filled zone sits at the authored clearance boundary",
            net="TARGET_ZONE_BOUNDARY",
            endpoints=(
                endpoint(
                    "J29",
                    "TARGET_ZONE_BOUNDARY",
                    approach_side="front",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    zone_clearance_mm=0.150499,
                ),
            ),
        ),
        RequiredTestAccess(
            mode="required",
            id="same-net-zone-control",
            basis="Synthetic close same-net filled zone is part of the target return domain",
            net="TARGET_ZONE_SAME_NET",
            endpoints=(
                endpoint(
                    "J30",
                    "TARGET_ZONE_SAME_NET",
                    approach_side="front",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    zone_clearance_mm=0.1,
                ),
            ),
        ),
        RequiredTestAccess(
            mode="required",
            id="filled-zone-hole-control",
            basis="Synthetic foreign-zone clearance hole remains outside the required probe envelope",
            net="TARGET_ZONE_HOLE",
            endpoints=(
                endpoint(
                    "J31",
                    "TARGET_ZONE_HOLE",
                    approach_side="front",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    zone_clearance_mm=0.1,
                ),
            ),
        ),
        RequiredTestAccess(
            mode="required",
            id="back-zone-clearance-fault",
            basis="Synthetic back-side foreign filled zone lies one nanometer inside the authored envelope",
            net="TARGET_ZONE_BACK_FAULT",
            endpoints=(
                endpoint(
                    "J32",
                    "TARGET_ZONE_BACK_FAULT",
                    approach_side="back",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    zone_clearance_mm=0.1505,
                ),
            ),
        ),
        RequiredTestAccess(
            mode="required",
            id="back-zone-clearance-boundary-control",
            basis="Synthetic back-side foreign filled zone sits at the authored clearance boundary",
            net="TARGET_ZONE_BACK_BOUNDARY",
            endpoints=(
                endpoint(
                    "J33",
                    "TARGET_ZONE_BACK_BOUNDARY",
                    approach_side="back",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    zone_clearance_mm=0.150499,
                ),
            ),
        ),
    )


def validate_zone_probe_fixture_observations(
    snapshot: PcbConnectivitySnapshot,
    observations: Mapping[tuple[str, str], PcbAccessProbeObservation],
) -> None:
    """Require exact zone identity, layer, net, island, and measured distance."""
    zones_by_identity = {
        (item.uuid.casefold(), item.layer.casefold()): item for item in snapshot.zones
    }
    for key, expected in ZONE_PROBE_EXPECTED_OBSERVATIONS.items():
        item = observations[key]
        observed = (
            item.zone_obstacle_uuid,
            item.zone_obstacle_layer,
            item.zone_obstacle_net,
            item.zone_obstacle_island_index,
            item.zone_obstacle_distance_nm,
        )
        if observed != expected:
            raise ValueError(
                f"Native zone geometry for {key[0]} {key[1]} differs from its fixture: "
                f"expected {expected}, found {observed}"
            )
        uuid, layer, _net, island_index, _distance = expected
        zone = zones_by_identity.get((uuid.casefold(), layer.casefold()))
        if zone is None or island_index not in {item.island_index for item in zone.filled_islands}:
            raise ValueError(
                f"Native zone geometry for {key[0]} has no matching filled-island inventory"
            )
