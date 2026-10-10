"""Typed context and setup for native switching-loop fixtures."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .hwrepo.models import ProjectConfig


class SwitchingLoopLog(Protocol):
    directory: Path

    def event(self, stage: str, status: str, **details: str | float) -> None: ...


@dataclass(slots=True)
class SwitchingLoopContext:
    root: Path
    project: str
    config: ProjectConfig
    fixture_root: Path
    scratch: Path
    cases: tuple[tuple[str, str, str, str, bool], ...]
    log: SwitchingLoopLog


def prepare_switching_loop_context(
    root: Path, project: str, image: str, log: SwitchingLoopLog
) -> SwitchingLoopContext:
    """Prepare native switching-loop fixture selection."""
    from .hwrepo.electrical import selected_config

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Switching-loop native fixtures do not cover KiCad {config.kicad_version}"
        )
    fixture_root = Path(__file__).resolve().parent / "hwrepo/fixtures"
    scratch = Path(
        tempfile.mkdtemp(prefix=f"pcb-switching-loop-{project}-", dir=log.directory.resolve())
    )
    cases = (
        ("front-plane", "pcb-switching-loop.kicad_pcb", "F.Cu", "CONNECTED", True),
        ("arc-trace", "pcb-switching-loop.kicad_pcb", "F.Cu", "CONNECTED", False),
        ("inner-plane", "pcb-switching-loop-inner-plane.kicad_pcb", "In1.Cu", "CONNECTED", False),
        ("split-inner-plane", "pcb-switching-loop-split-plane.kicad_pcb", "In1.Cu", "SPLIT", False),
    )
    return SwitchingLoopContext(
        root=root,
        project=project,
        config=config,
        fixture_root=fixture_root,
        scratch=scratch,
        cases=cases,
        log=log,
    )
