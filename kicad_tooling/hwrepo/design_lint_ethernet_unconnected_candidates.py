"""Coordinate Ethernet data and management open-pin candidates."""

from __future__ import annotations

from .bus_ethernet_unconnected_data import ethernet_data_unconnected_pin_candidates
from .bus_ethernet_unconnected_management import ethernet_management_unconnected_pin_candidates
from .design_lint_types import Candidate
from .models import NetlistContract


def ethernet_unconnected_pin_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Combine the focused Ethernet data-pair and management-pair checks."""
    return (
        *ethernet_management_unconnected_pin_candidates(observed),
        *ethernet_data_unconnected_pin_candidates(observed),
    )
