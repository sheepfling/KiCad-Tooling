"""Layer-aware pad-center distance for PCB decoupling review."""

from __future__ import annotations

from typing import Literal

from .pcb_connectivity_observations import PcbPadConnectivityObservation


def nearest_outer_copper_center_distance_squared(
    first: PcbPadConnectivityObservation | None,
    second: PcbPadConnectivityObservation | None,
    board_thickness_nm: int | None,
) -> tuple[int, Literal["F.Cu", "B.Cu"], Literal["F.Cu", "B.Cu"]] | None:
    """Measure the closest outer-copper pad centers using board thickness across sides."""
    if (
        first is None
        or second is None
        or board_thickness_nm is None
        or not first.outer_copper_centers
        or not second.outer_copper_centers
    ):
        return None
    return min(
        (
            (left.x_nm - right.x_nm) ** 2
            + (left.y_nm - right.y_nm) ** 2
            + (0 if left.layer == right.layer else board_thickness_nm) ** 2,
            left.layer,
            right.layer,
        )
        for left in first.outer_copper_centers
        for right in second.outer_copper_centers
    )
