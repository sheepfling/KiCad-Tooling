"""Shared synthetic fixtures for the switching-loop geometry and route tests."""

from __future__ import annotations

from tests.design_lint_fixtures.pcb_switching_loop_core import (
    IMAGE,
    PLANE_UUID,
    PLANE_UUID_2,
    loop_pad,
    mapping,
    requirement,
    snapshot,
)
from tests.design_lint_fixtures.pcb_switching_loop_reports import (
    coach,
    coverage,
    design_lint_report,
)
from tests.design_lint_fixtures.pcb_switching_loop_routes import (
    contoured_snapshot,
    long_routed_snapshot,
    route_track,
    routed_mapping,
    routed_snapshot,
    via_routed_snapshot,
)

__all__ = [
    "IMAGE",
    "PLANE_UUID",
    "PLANE_UUID_2",
    "coach",
    "contoured_snapshot",
    "coverage",
    "design_lint_report",
    "long_routed_snapshot",
    "loop_pad",
    "mapping",
    "requirement",
    "route_track",
    "routed_mapping",
    "routed_snapshot",
    "snapshot",
    "via_routed_snapshot",
]
