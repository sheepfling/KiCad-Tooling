"""Collect I2C and I3C signal-pair review candidates in stable order."""

from __future__ import annotations

from .design_lint_types import Candidate
from .i2c_same_net import i2c_sda_scl_same_net_candidates
from .i2c_signal_label import i2c_signal_label_role_candidates
from .i2c_signal_named_rail import i2c_signal_on_named_rail_candidates
from .i3c_same_net import i3c_sda_scl_same_net_candidates
from .i3c_signal_named_rail import i3c_signal_on_named_rail_candidates
from .models import NetlistContract


def two_wire_signal_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Collect I2C and I3C signal checks without owning their predicates."""
    return (
        *i2c_signal_label_role_candidates(observed),
        *i2c_signal_on_named_rail_candidates(observed),
        *i3c_signal_on_named_rail_candidates(observed),
        *i3c_sda_scl_same_net_candidates(observed),
        *i2c_sda_scl_same_net_candidates(observed),
    )
