"""Coordinate independent hosted PCB geometry fixture themes."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_pcb_decoupling_fixture import decoupling_placement_fixture_lane
from .ci_hosted_pcb_fixture_support import HostedPcbFixtureFailure
from .ci_hosted_pcb_protection_fixture import protection_path_fixture_lane
from .ci_hosted_pcb_track_width_fixture import track_width_fixture_lane

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def pcb_decoupling_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Run independent decoupling, protection-path, and track-width controls."""
    failures: list[HostedPcbFixtureFailure] = []
    for lane in (
        decoupling_placement_fixture_lane,
        protection_path_fixture_lane,
        track_width_fixture_lane,
    ):
        try:
            lane(root, project=project, image=image, log=log)
        except HostedPcbFixtureFailure as exc:
            failures.append(exc)
    if failures:
        raise failures[0]
