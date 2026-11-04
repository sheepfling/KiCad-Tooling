"""Match source-bound PCB evidence to the current board inventory."""

from __future__ import annotations

from .model_primitives import Digest, RepositoryPath
from .source_state_models import SourceHashInventory


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
