"""Coordinate USB-C connector and controller same-net review rules."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .usb_c_cc_controller_same_net import usb_c_cc_controller_same_net_candidates
from .usb_c_cc_same_net import usb_c_cc_same_net_candidates


def usb_c_same_net_candidates(
    observed: NetlistContract, reviewed_connector_references: tuple[str, ...] = ()
) -> tuple[Candidate, ...]:
    """Run the separately owned CC connector and controller predicates."""
    return (
        *usb_c_cc_same_net_candidates(observed, reviewed_connector_references),
        *usb_c_cc_controller_same_net_candidates(observed),
    )
