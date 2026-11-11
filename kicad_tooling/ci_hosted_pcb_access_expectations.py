"""Expected native pad and status records for the synthetic access fixture."""

from __future__ import annotations

from .ci_hosted_pcb_access_edges import EDGE_PROBE_EXPECTED_STATUSES
from .ci_hosted_pcb_access_holes import HOLE_PROBE_EXPECTED_STATUSES
from .ci_hosted_pcb_access_tracks import TRACK_PROBE_EXPECTED_STATUSES
from .ci_hosted_pcb_access_vias import (
    VIA_PROBE_EXPECTED_PAD_OBSERVATIONS,
    VIA_PROBE_EXPECTED_STATUSES,
)
from .ci_hosted_pcb_access_zones import ZONE_PROBE_EXPECTED_STATUSES

_ACCESS_PROBE_EXPECTED_STATUSES = {
    "test-access/pcb-probe-envelope/front-back-boundary": "PASS",
    "test-access/pcb-probe-envelope/unconnected-obstacle": "NOT_RUN",
    "test-access/pcb-probe-envelope/front-only-clearance-fault": "FAIL",
    "test-access/pcb-probe-envelope/undersize-aperture-fault": "FAIL",
    "test-access/pcb-probe-envelope/aperture-fit-boundary-control": "PASS",
    "test-access/pcb-probe-envelope/rectangular-aperture-boundary-control": "PASS",
    "test-access/pcb-probe-envelope/drilled-aperture-unsupported": "FAIL",
    "test-access/pcb-probe-envelope/undersize-oval-aperture-fault": "FAIL",
    "test-access/pcb-probe-envelope/oval-aperture-boundary-control": "PASS",
    "test-access/pcb-probe-envelope/undersize-roundrect-aperture-fault": "FAIL",
    "test-access/pcb-probe-envelope/roundrect-aperture-boundary-control": "PASS",
    "test-access/pcb-probe-envelope/courtyard-clearance-fault": "FAIL",
    **VIA_PROBE_EXPECTED_STATUSES,
    **TRACK_PROBE_EXPECTED_STATUSES,
    **ZONE_PROBE_EXPECTED_STATUSES,
    **EDGE_PROBE_EXPECTED_STATUSES,
    **HOLE_PROBE_EXPECTED_STATUSES,
}

_ACCESS_PROBE_EXPECTED_PAD_OBSERVATIONS = {
    ("j1.1", "front"): ("J4.1", "FOREIGN_FRONT", 400_000, True, "circle", 1_200_000),
    ("j1.1", "back"): ("J5.1", "FOREIGN_BACK", 800_000, True, "circle", 1_200_000),
    ("j7.1", "front"): ("J8.1", None, 400_000, True, "circle", 800_000),
    ("j9.1", "front"): (
        "J10.1",
        "FOREIGN_FRONT_ONLY",
        400_000,
        True,
        "circle",
        300_000,
    ),
    ("j9.1", "back"): (None, None, None, False, None, None),
    ("j11.1", "front"): (
        "J12.1",
        "TARGET_APERTURE_BOUNDARY",
        9_500_001,
        True,
        "circle",
        400_000,
    ),
    ("j12.1", "front"): (
        "J13.1",
        "TARGET_APERTURE_RECT",
        9_400_000,
        True,
        "circle",
        800_000,
    ),
    ("j13.1", "front"): (
        "J12.1",
        "TARGET_APERTURE_BOUNDARY",
        9_500_001,
        True,
        "rectangle",
        800_000,
    ),
    ("j14.1", "front"): (
        "J13.1",
        "TARGET_APERTURE_RECT",
        9_400_000,
        True,
        "unsupported",
        None,
    ),
    ("j15.1", "front"): (
        "J16.1",
        "TARGET_APERTURE_OVAL_BOUNDARY",
        9_400_001,
        True,
        "oval",
        600_000,
    ),
    ("j16.1", "front"): (
        "J15.1",
        "TARGET_APERTURE_OVAL_SMALL",
        9_400_001,
        True,
        "oval",
        800_000,
    ),
    ("j17.1", "front"): (
        "J16.1",
        "TARGET_APERTURE_OVAL_BOUNDARY",
        9_400_001,
        True,
        "roundrect",
        600_000,
    ),
    ("j18.1", "front"): (
        "J19.1",
        "TARGET_COURTYARD_SMALL",
        9_500_001,
        True,
        "roundrect",
        800_000,
    ),
    ("j19.1", "front"): (
        "J18.1",
        "TARGET_APERTURE_ROUNDRECT_BOUNDARY",
        9_600_000,
        True,
        "circle",
        1_000_000,
    ),
    ("j36.1", "front"): (
        "J37.1",
        "TARGET_HOLE_FAULT",
        9_400_001,
        True,
        "circle",
        1_200_000,
    ),
    ("j37.1", "front"): (
        "J36.1",
        "TARGET_HOLE_BOUNDARY",
        9_400_001,
        True,
        "circle",
        1_200_000,
    ),
    **VIA_PROBE_EXPECTED_PAD_OBSERVATIONS,
    ("j24.1", "front"): (
        "J25.1",
        "TARGET_TRACK_BOUNDARY",
        9_750_001,
        True,
        "circle",
        800_000,
    ),
    ("j25.1", "front"): (
        "J24.1",
        "TARGET_TRACK_FAULT",
        9_750_001,
        True,
        "circle",
        800_000,
    ),
    ("j26.1", "back"): (
        "J23.1",
        "TARGET_BACK_VIA",
        89_750_001,
        True,
        "circle",
        800_000,
    ),
    ("j27.1", "front"): (
        "J25.1",
        "TARGET_TRACK_BOUNDARY",
        19_750_001,
        True,
        "circle",
        800_000,
    ),
    ("j28.1", "front"): (
        "J29.1",
        "TARGET_ZONE_BOUNDARY",
        9_750_001,
        True,
        "circle",
        800_000,
    ),
    ("j29.1", "front"): (
        "J28.1",
        "TARGET_ZONE_FAULT",
        9_750_001,
        True,
        "circle",
        800_000,
    ),
    ("j30.1", "front"): (
        "J29.1",
        "TARGET_ZONE_BOUNDARY",
        9_750_001,
        True,
        "circle",
        800_000,
    ),
    ("j31.1", "front"): (
        "J30.1",
        "TARGET_ZONE_SAME_NET",
        9_750_001,
        True,
        "circle",
        800_000,
    ),
    ("j32.1", "back"): (
        "J33.1",
        "TARGET_ZONE_BACK_BOUNDARY",
        9_750_001,
        True,
        "circle",
        800_000,
    ),
    ("j33.1", "back"): (
        "J32.1",
        "TARGET_ZONE_BACK_FAULT",
        9_750_001,
        True,
        "circle",
        800_000,
    ),
    ("j34.1", "front"): (
        "J35.1",
        "TARGET_EDGE_FAULT",
        18_500_001,
        True,
        "circle",
        1_000_000,
    ),
    ("j35.1", "front"): (
        "J34.1",
        "TARGET_EDGE_BOUNDARY",
        18_500_001,
        True,
        "circle",
        1_000_000,
    ),
    ("j38.1", "front"): (
        "J39.1",
        "TARGET_OBLONG_HOLE_FAULT",
        17_400_002,
        True,
        "circle",
        1_200_000,
    ),
    ("j39.1", "front"): (
        "J38.1",
        "TARGET_OBLONG_HOLE_BOUNDARY",
        17_400_002,
        True,
        "circle",
        1_200_000,
    ),
}

_EXPECTED_COURTYARDS = {
    ("j7.1", "front"): ("U1", 100_400_000, "J8", 250_000),
    ("j18.1", "front"): ("U1", 400_000, "J17", 9_400_000),
    ("j19.1", "front"): ("U2", 399_999, "J18", 9_400_000),
}


def expected_access_probe_statuses() -> dict[str, str]:
    """Return deterministic fault and control statuses for the full fixture."""
    return dict(_ACCESS_PROBE_EXPECTED_STATUSES)


def expected_access_probe_pad_observations() -> dict[
    tuple[str, str], tuple[str | None, str | None, int | None, bool, str | None, int | None]
]:
    """Return expected native pad-obstacle and aperture evidence."""
    return dict(_ACCESS_PROBE_EXPECTED_PAD_OBSERVATIONS)


def expected_access_probe_courtyards() -> dict[tuple[str, str], tuple[str, int, str, int]]:
    """Return expected measured and unmeasured courtyard evidence."""
    return dict(_EXPECTED_COURTYARDS)
