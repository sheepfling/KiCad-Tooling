"""Bind retained PCB geometry receipts to the typed evidence being evaluated."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .command_evidence_models import CommandEvidence
from .contracts import parse_model_text
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot


def write_pcb_geometry_snapshot(path: Path, snapshot: PcbConnectivitySnapshot) -> None:
    """Keep explicit null observations required by versioned snapshot schemas."""
    path.write_text(snapshot.model_dump_json(by_alias=True, indent=2) + "\n", encoding="utf-8")


def verify_pcb_geometry_receipts(
    snapshot: PcbConnectivitySnapshot,
    snapshot_path: Path,
    snapshot_sha256: str,
    command: CommandEvidence,
    command_path: Path,
    command_sha256: str,
) -> None:
    """Require the retained bytes, recorded digests, and parsed records to agree."""
    for label, path, expected_hash, expected_model, model_type in (
        ("snapshot", snapshot_path, snapshot_sha256, snapshot, PcbConnectivitySnapshot),
        ("command", command_path, command_sha256, command, CommandEvidence),
    ):
        try:
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected_hash:
                raise ValueError("digest mismatch")
            if parse_model_text(raw.decode("utf-8"), model_type) != expected_model:
                raise ValueError("typed record mismatch")
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError(f"Native PCB {label} differs from source-bound evidence") from exc
