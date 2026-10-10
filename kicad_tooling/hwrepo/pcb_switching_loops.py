"""Compatibility facade for deterministic switching-loop review."""

from __future__ import annotations

from .pcb_switching_loop_review import pcb_switching_loop_entries
from .pcb_switching_loop_route_topology import (
    resolve_switching_loop_trace_edge as _resolve_trace_edge,
)

__all__ = ["_resolve_trace_edge", "pcb_switching_loop_entries"]
