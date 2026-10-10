"""Coordinate native PCB return-path fixture setup and per-case checks."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_pcb_return_case import verify_pcb_return_fixture_case
from .ci_hosted_pcb_return_context import PcbReturnLog, prepare_pcb_return_fixture_context


def run_pcb_return_fixture_lane(root: Path, *, project: str, image: str, log: PcbReturnLog) -> None:
    """Run every synthetic PCB return-path fixture against pinned native evidence."""
    context = prepare_pcb_return_fixture_context(root, project, image, log)
    for fixture_case in context.fixtures:
        verify_pcb_return_fixture_case(context, fixture_case)
