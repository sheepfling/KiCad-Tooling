"""Coordinate native switching-loop fixture setup and geometry checks."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_pcb_switching_loop_context import SwitchingLoopLog, prepare_switching_loop_context
from .ci_hosted_pcb_switching_loop_geometry import verify_switching_loop_geometry_cases


def run_switching_loop_fixture_lane(
    root: Path, *, project: str, image: str, log: SwitchingLoopLog
) -> None:
    """Run source-bound switching-loop fixture cases."""
    context = prepare_switching_loop_context(root, project, image, log)
    verify_switching_loop_geometry_cases(context)
