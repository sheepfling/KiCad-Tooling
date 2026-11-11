"""Synthetic Edge.Cuts clearance scenarios for native probe acceptance."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from .hwrepo.pcb_connectivity_observations import PcbAccessProbeObservation
from .hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .hwrepo.pcb_test_access_models import RequiredTestAccess, TestAccessEndpointRequirement

EDGE_PROBE_EXPECTED_STATUSES = {
    "test-access/pcb-probe-envelope/board-edge-boundary-control": "PASS",
    "test-access/pcb-probe-envelope/board-edge-clearance-fault": "FAIL",
}

EDGE_PROBE_EXPECTED_OBSERVATIONS = {
    ("j34.1", "front"): ("00000000-0000-0000-0000-000000000058", 375_000),
    ("j35.1", "front"): ("00000000-0000-0000-0000-000000000062", 375_000),
}


def edge_probe_fixture_decisions(
    endpoint: Callable[..., TestAccessEndpointRequirement],
) -> tuple[RequiredTestAccess, ...]:
    """Build exact-boundary and one-nanometer-inside edge clearance requirements."""
    return (
        RequiredTestAccess(
            mode="required",
            id="board-edge-boundary-control",
            basis="Synthetic outer Edge.Cuts stroke matches the authored probe clearance",
            net="TARGET_EDGE_BOUNDARY",
            endpoints=(
                endpoint(
                    "J34",
                    "TARGET_EDGE_BOUNDARY",
                    approach_side="front",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    board_edge_clearance_mm=0.075,
                ),
            ),
        ),
        RequiredTestAccess(
            mode="required",
            id="board-edge-clearance-fault",
            basis="Synthetic internal Edge.Cuts stroke is one nanometer inside the authored envelope",
            net="TARGET_EDGE_FAULT",
            endpoints=(
                endpoint(
                    "J35",
                    "TARGET_EDGE_FAULT",
                    approach_side="front",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    board_edge_clearance_mm=0.075001,
                ),
            ),
        ),
    )


def validate_edge_probe_fixture_observations(
    snapshot: PcbConnectivitySnapshot,
    observations: Mapping[tuple[str, str], PcbAccessProbeObservation],
) -> None:
    """Require exact native Edge.Cuts identities and target-center distances."""
    inventory = {item.uuid.casefold(): item.width_nm for item in snapshot.edge_cuts}
    for key, expected in EDGE_PROBE_EXPECTED_OBSERVATIONS.items():
        item = observations[key]
        observed = (item.edge_obstacle_uuid, item.edge_obstacle_distance_nm)
        if observed != expected:
            raise ValueError(
                f"Native Edge.Cuts geometry for {key[0]} {key[1]} differs from its fixture: "
                f"expected {expected}, found {observed}"
            )
        uuid, _distance = expected
        if inventory.get(uuid.casefold()) != 50_000:
            raise ValueError(
                f"Native Edge.Cuts geometry for {key[0]} has no matching 50,000 nm inventory item"
            )
