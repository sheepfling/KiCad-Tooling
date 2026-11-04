"""Collect I2C and I3C signal-pair review candidates in stable order."""

from __future__ import annotations

from .design_lint_i3c_unconnected_candidate_evidence import (
    I3cUnconnectedCandidate,
    I3cUnconnectedFindingEvidence,
)
from .design_lint_types import Candidate
from .i2c_same_net import i2c_sda_scl_same_net_candidates
from .i2c_signal_label import i2c_signal_label_role_candidates
from .i2c_signal_named_rail import i2c_signal_on_named_rail_candidates
from .i3c_same_net import i3c_sda_scl_same_net_candidates
from .i3c_signal_named_rail import i3c_signal_on_named_rail_candidates
from .i3c_unconnected_pins import unconnected_i3c_signal_pins
from .netlist_contract_models import NetlistContract


def two_wire_signal_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Collect I2C and I3C signal checks without owning their predicates."""
    return (
        *i2c_signal_label_role_candidates(observed),
        *i2c_signal_on_named_rail_candidates(observed),
        *i3c_signal_on_named_rail_candidates(observed),
        *i3c_unconnected_signal_candidates(observed),
        *i3c_sda_scl_same_net_candidates(observed),
        *i2c_sda_scl_same_net_candidates(observed),
    )


def i3c_unconnected_signal_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Translate one-sided open I3C signal observations into REVIEW candidates."""
    return tuple(
        I3cUnconnectedCandidate.from_source_evidence(
            I3cUnconnectedFindingEvidence(pin),
            subject=f"{pin.pin}: {pin.function}",
            message=(
                f"This I3C {pin.role} function on channel {pin.channel or 'unindexed'} is "
                f"unassigned while its paired {pin.paired_function} pin {pin.paired_pin} "
                f"is assigned to {pin.paired_net}. Review whether this partial I3C path "
                "is intentional or a connection is missing. Function names do not "
                "establish bus use or PCB routing."
            ),
        )
        for pin in unconnected_i3c_signal_pins(observed)
    )
