"""Read and match source-bound PCB board inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .contracts import read_regular_bytes, repo_path
from .model_primitives import Digest, RepositoryPath
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_MAX_PCB_SOURCE_BYTES = 128 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class SourceBoundPcbBoard:
    """Exact board bytes whose current source digest matches the inventory."""

    local_path: Path
    relative_path: str
    sha256: str
    source: bytes


def read_source_bound_pcb_board(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> SourceBoundPcbBoard | None:
    """Read one current PCB board only when its path and digest are inventoried."""
    if config.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        return None

    project_relative = Path(str(config.project)).as_posix()
    relative_path = Path(project_relative).with_suffix(".kicad_pcb").as_posix()
    expected_hash = source_hashes.get(relative_path)
    if expected_hash is None:
        return None

    local_path = repo_path(root, relative_path)
    source, _state = read_regular_bytes(local_path, maximum=_MAX_PCB_SOURCE_BYTES)
    # Evidence imports report models, which can reach this PCB binding module
    # during model initialization. Keep the canonical digest service lazy so
    # that source-bound PCB readers remain safe in that import path.
    from .evidence import digest_bytes

    source_sha256 = digest_bytes(source)
    if source_sha256 != expected_hash:
        raise ValueError(f"PCB source differs from the source-bound hashes: {relative_path}")
    return SourceBoundPcbBoard(
        local_path=local_path,
        relative_path=relative_path,
        sha256=source_sha256,
        source=source,
    )


def verify_source_bound_pcb_board_unchanged(board: SourceBoundPcbBoard) -> None:
    """Reject a board that changed while a source-bound analysis was running."""
    from .evidence import digest

    if digest(board.local_path) != board.sha256:
        raise ValueError(f"PCB source changed while scanning: {board.relative_path}")


def pcb_board_source_matches(
    board_path: RepositoryPath | None,
    board_sha256: Digest | None,
    source_hashes: SourceHashInventory,
) -> bool:
    """Return whether a report names the board at its current source hash."""
    return bool(
        board_path is not None
        and board_sha256 is not None
        and source_hashes.get(board_path) == board_sha256
    )
