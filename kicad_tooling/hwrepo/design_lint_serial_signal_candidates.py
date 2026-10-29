"""Collect serial signal checks in stable order."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .serial_endpoint_role_collision import serial_endpoint_role_collision_candidates
from .serial_same_net import serial_tx_rx_same_net_candidates
from .serial_signal_named_rail import serial_signal_on_named_rail_candidates
from .serial_tx_output_sharing import serial_tx_output_sharing_candidates
from .serial_tx_rx_label_mismatch import serial_tx_rx_label_mismatch_candidates


def serial_signal_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Collect serial signal checks without owning their predicates."""
    return (
        *serial_tx_rx_label_mismatch_candidates(observed),
        *serial_signal_on_named_rail_candidates(observed),
        *serial_tx_rx_same_net_candidates(observed),
        *serial_endpoint_role_collision_candidates(observed),
        *serial_tx_output_sharing_candidates(observed),
    )
