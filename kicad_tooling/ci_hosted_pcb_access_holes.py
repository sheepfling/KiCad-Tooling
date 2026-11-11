"""Synthetic drilled-opening scenarios for native probe-envelope acceptance."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from .hwrepo.pcb_connectivity_observations import PcbAccessProbeObservation
from .hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .hwrepo.pcb_test_access_models import RequiredTestAccess, TestAccessEndpointRequirement

HOLE_PROBE_EXPECTED_STATUSES = {
    "test-access/pcb-probe-envelope/drill-hole-boundary-control": "PASS",
    "test-access/pcb-probe-envelope/drill-hole-clearance-fault": "FAIL",
}

HOLE_PROBE_EXPECTED_OBSERVATIONS = {
    ("j36.1", "front"): ("pad:00000000-0000-0000-0000-0000000000a1", 500_001),
    ("j37.1", "front"): ("pad:00000000-0000-0000-0000-0000000000a2", 500_000),
}


def hole_probe_fixture_decisions(
    endpoint: Callable[..., TestAccessEndpointRequirement],
) -> tuple[RequiredTestAccess, ...]:
    """Build exact-boundary and one-nanometer-inside drill-hole requirements."""
    return (
        RequiredTestAccess(
            mode="required",
            id="drill-hole-boundary-control",
            basis="Synthetic NPTH opening meets the project-authored probe clearance exactly",
            net="TARGET_HOLE_BOUNDARY",
            endpoints=(
                endpoint(
                    "J36",
                    "TARGET_HOLE_BOUNDARY",
                    approach_side="front",
                    tip_diameter_mm=0.8,
                    clearance_mm=0.05,
                    drill_hole_clearance_mm=0.100001,
                ),
            ),
        ),
        RequiredTestAccess(
            mode="required",
            id="drill-hole-clearance-fault",
            basis="Synthetic NPTH opening is one nanometer inside the project-authored clearance",
            net="TARGET_HOLE_FAULT",
            endpoints=(
                endpoint(
                    "J37",
                    "TARGET_HOLE_FAULT",
                    approach_side="front",
                    tip_diameter_mm=0.8,
                    clearance_mm=0.05,
                    drill_hole_clearance_mm=0.100001,
                ),
            ),
        ),
    )


def validate_hole_probe_fixture_observations(
    snapshot: PcbConnectivitySnapshot,
    observations: Mapping[tuple[str, str], PcbAccessProbeObservation],
) -> None:
    """Require native IDs, NPTH geometry, via surface access, and exact distances."""
    holes = {item.id.casefold(): item for item in snapshot.drill_holes}
    for key, expected in HOLE_PROBE_EXPECTED_OBSERVATIONS.items():
        item = observations[key]
        observed = (item.hole_obstacle_id, item.hole_obstacle_distance_nm)
        if observed != expected:
            raise ValueError(
                f"Native drill-hole geometry for {key[0]} {key[1]} differs from its fixture: "
                f"expected {expected}, found {observed}"
            )
        identity, _distance_nm = expected
        hole = holes.get(identity.casefold())
        if (
            hole is None
            or hole.kind != "pad"
            or hole.footprint_reference != ("H1" if key[0] == "j36.1" else "H2")
            or hole.drill_size_nm != (500_000, 500_000)
            or hole.shape != "circle"
            or "front" not in hole.surfaces
        ):
            raise ValueError(f"Native drill-hole identity for {key[0]} has invalid source geometry")

    via_surfaces = {
        item.position_nm: item.surfaces for item in snapshot.drill_holes if item.kind == "via"
    }
    expected_vias = {
        (140_699_999, 5_000_000): ("front",),
        (149_450_000, 5_000_000): ("front",),
        (170_700_000, 5_000_000): ("back",),
    }
    for position, surfaces in expected_vias.items():
        if via_surfaces.get(position) != surfaces:
            raise ValueError(
                f"Native drill-hole via at {position} should be open on {surfaces}, "
                f"found {via_surfaces.get(position)}"
            )
    if (160_600_000, 5_000_000) in via_surfaces:
        raise ValueError("Native tented via drill opening must not be surface-accessible")
