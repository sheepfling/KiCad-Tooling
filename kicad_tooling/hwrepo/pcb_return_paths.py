"""Compatibility facade for PCB return-path evaluation and native evidence."""

from __future__ import annotations

from .pcb_return_path_capture import (
    NATIVE_PROBE_SOURCE_PARTS,
    capture_native_pcb_connectivity,
    expected_probe_sha256,
    native_pcb_command_matches,
    native_probe_source,
)
from .pcb_return_path_checks import pcb_return_path_checks

__all__ = [
    "NATIVE_PROBE_SOURCE_PARTS",
    "capture_native_pcb_connectivity",
    "expected_probe_sha256",
    "native_pcb_command_matches",
    "native_probe_source",
    "pcb_return_path_checks",
]
