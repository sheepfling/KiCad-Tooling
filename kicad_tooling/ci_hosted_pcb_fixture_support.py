"""Shared, source-bound setup for hosted native PCB fixture lanes."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.models import ProjectConfig
from .hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


class HostedPcbFixtureFailure(RuntimeError):
    """A theme lane failed after it recorded its failure evidence."""


@dataclass(frozen=True)
class HostedPcbFixtureContext:
    root: Path
    project: str
    config: ProjectConfig
    scratch: Path
    fixture_root: Path


def prepare_pcb_fixture(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
    lane: str,
    scratch_prefix: str,
) -> HostedPcbFixtureContext:
    """Resolve the reviewed toolchain and allocate an in-checkout receipt area."""
    from .hwrepo.electrical import selected_config

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"{lane} native fixtures do not cover KiCad {config.kicad_version}")
    scratch = Path(
        tempfile.mkdtemp(prefix=f"{scratch_prefix}-{project}-", dir=log.directory.resolve())
    )
    return HostedPcbFixtureContext(
        root=root,
        project=project,
        config=config,
        scratch=scratch,
        fixture_root=Path(__file__).resolve().parent / "hwrepo/fixtures",
    )


def capture_verified_pcb_snapshot(
    context: HostedPcbFixtureContext,
    config: ProjectConfig,
    receipt: Path,
    *,
    expected_board_sha256: str,
    purpose: str,
    require_outer_copper: bool = False,
) -> PcbConnectivitySnapshot:
    """Capture native geometry and bind it to the exact board, tool, and probe."""
    from .hwrepo.pcb_return_path_capture import (
        capture_native_pcb_connectivity,
        expected_probe_sha256,
        native_pcb_command_matches,
    )

    command, snapshot = capture_native_pcb_connectivity(context.root, config, receipt)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(f"Native {purpose} command failed: {command.stderr or command.error}")
    if not native_pcb_command_matches(command, config):
        raise ValueError(f"Native {purpose} did not use the pinned read-only probe command")
    if snapshot is None:
        raise ValueError(f"Native {purpose} returned no connectivity snapshot")
    if (
        snapshot.schema_version not in {"10", "11", "12"}
        or snapshot.board_sha256 != expected_board_sha256
        or snapshot.kicad_version != context.config.kicad_version
        or snapshot.image != context.config.image
        or snapshot.probe_sha256 != expected_probe_sha256()
        or not snapshot.zones_refilled
    ):
        raise ValueError(f"Native {purpose} evidence is not bound to its exact source and tool")
    if require_outer_copper and (
        not snapshot.copper_layers
        or snapshot.copper_layers[0].casefold() != "f.cu"
        or snapshot.copper_layers[-1].casefold() != "b.cu"
    ):
        raise ValueError(f"Native {purpose} evidence does not contain the expected copper stack")
    return snapshot
