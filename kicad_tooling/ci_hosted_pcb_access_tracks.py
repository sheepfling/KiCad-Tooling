"""Synthetic exposed-surface track-clearance scenarios for native probe acceptance."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from .hwrepo.pcb_connectivity_observations import PcbAccessProbeObservation
from .hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .hwrepo.pcb_test_access_models import RequiredTestAccess, TestAccessEndpointRequirement

TRACK_PROBE_EXPECTED_STATUSES = {
    "test-access/pcb-probe-envelope/track-clearance-fault": "FAIL",
    "test-access/pcb-probe-envelope/track-clearance-boundary-control": "PASS",
    "test-access/pcb-probe-envelope/same-net-track-control": "PASS",
    "test-access/pcb-probe-envelope/unconnected-track-arc-fault": "FAIL",
}

TRACK_PROBE_EXPECTED_OBSERVATIONS = {
    ("j24.1", "front"): (
        "00000000-0000-0000-0000-000000000040",
        "FOREIGN_TRACK_FAULT",
        400_000,
        "segment",
    ),
    ("j25.1", "front"): (
        "00000000-0000-0000-0000-000000000041",
        "FOREIGN_TRACK_BOUNDARY",
        400_000,
        "segment",
    ),
    ("j26.1", "back"): (None, None, None, None),
    ("j27.1", "front"): (
        "00000000-0000-0000-0000-000000000043",
        None,
        400_001,
        "arc",
    ),
}


def track_probe_fixture_decisions(
    endpoint: Callable[..., TestAccessEndpointRequirement],
) -> tuple[RequiredTestAccess, ...]:
    """Build exact-boundary and fault requirements for native track measurements."""
    return (
        RequiredTestAccess(
            mode="required",
            id="track-clearance-fault",
            basis="Synthetic different-net track lies one nanometer inside the authored envelope",
            net="TARGET_TRACK_FAULT",
            endpoints=(
                endpoint(
                    "J24",
                    "TARGET_TRACK_FAULT",
                    approach_side="front",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    track_clearance_mm=0.100001,
                ),
            ),
        ),
        RequiredTestAccess(
            mode="required",
            id="track-clearance-boundary-control",
            basis="Synthetic foreign track sits at the exact authored clearance boundary",
            net="TARGET_TRACK_BOUNDARY",
            endpoints=(
                endpoint(
                    "J25",
                    "TARGET_TRACK_BOUNDARY",
                    approach_side="front",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    track_clearance_mm=0.1,
                ),
            ),
        ),
        RequiredTestAccess(
            mode="required",
            id="same-net-track-control",
            basis="Synthetic close same-net track does not obstruct the authored access net",
            net="TARGET_TRACK_SAME_NET",
            endpoints=(
                endpoint(
                    "J26",
                    "TARGET_TRACK_SAME_NET",
                    approach_side="back",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    track_clearance_mm=0.1,
                ),
            ),
        ),
        RequiredTestAccess(
            mode="required",
            id="unconnected-track-arc-fault",
            basis="Synthetic unconnected copper arc lies one nanometer inside the authored envelope",
            net="TARGET_TRACK_ARC",
            endpoints=(
                endpoint(
                    "J27",
                    "TARGET_TRACK_ARC",
                    approach_side="front",
                    tip_diameter_mm=0.6,
                    clearance_mm=0.1,
                    track_clearance_mm=0.100002,
                ),
            ),
        ),
    )


def validate_track_probe_fixture_observations(
    snapshot: PcbConnectivitySnapshot,
    observations: Mapping[tuple[str, str], PcbAccessProbeObservation],
) -> None:
    """Require exact track UUID, net, geometry kind, side, and measured distance."""
    for key, expected in TRACK_PROBE_EXPECTED_OBSERVATIONS.items():
        item = observations[key]
        observed = (
            item.track_obstacle_uuid,
            item.track_obstacle_net,
            item.track_obstacle_distance_nm,
            item.track_obstacle_geometry,
        )
        if observed != expected:
            raise ValueError(
                f"Native track geometry for {key[0]} {key[1]} differs from its fixture: "
                f"expected {expected}, found {observed}"
            )
    tracks_by_id = {item.uuid.casefold(): item for item in snapshot.tracks}
    for key, expected in TRACK_PROBE_EXPECTED_OBSERVATIONS.items():
        identity = expected[0]
        if identity is None:
            continue
        track = tracks_by_id.get(identity.casefold())
        layer = "F.Cu" if key[1] == "front" else "B.Cu"
        if track is None or track.layer.casefold() != layer.casefold():
            raise ValueError(f"Native track geometry for {key[0]} uses the wrong fixture layer")
