"""Collect interface signal candidates assigned to explicitly named rails."""

from __future__ import annotations

from .bus_ethernet_management_named_rail import (
    ethernet_management_signal_on_named_rail_candidates,
)
from .bus_ethernet_signal_named_rail import ethernet_signal_on_named_rail_candidates
from .bus_usb_signal_named_rail import usb_signal_on_named_rail_candidates
from .design_lint_types import Candidate
from .models import NetlistContract
from .usb_c_cc_named_rail import usb_c_cc_signal_on_named_rail_candidates
from .usb_c_sbu_named_rail import usb_c_sbu_signal_on_named_rail_candidates


def bus_named_rail_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Return named-rail prompts in the established interface-rule order."""
    return (
        *ethernet_management_signal_on_named_rail_candidates(observed),
        *ethernet_signal_on_named_rail_candidates(observed),
        *usb_signal_on_named_rail_candidates(observed),
        *usb_c_cc_signal_on_named_rail_candidates(observed),
        *usb_c_sbu_signal_on_named_rail_candidates(observed),
    )
