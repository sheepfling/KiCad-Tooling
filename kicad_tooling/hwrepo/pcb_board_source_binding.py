"""Match source-bound PCB evidence to the current board inventory."""

from __future__ import annotations

from collections.abc import Mapping


def pcb_board_source_matches(
    board_path: str | None,
    board_sha256: str | None,
    source_hashes: Mapping[str, str],
) -> bool:
    """Return whether a report names the board at its current source hash."""
    return bool(
        board_path is not None
        and board_sha256 is not None
        and source_hashes.get(board_path) == board_sha256
    )
