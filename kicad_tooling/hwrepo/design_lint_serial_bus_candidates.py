"""Coordinate native serial signal and generic-connector candidates."""

from __future__ import annotations

from .design_lint_bus_inputs import BusCandidateInputs
from .design_lint_serial_generic_connector_candidates import (
    serial_generic_connector_pair_review_candidates,
)
from .design_lint_serial_signal_candidates import serial_signal_candidates
from .design_lint_types import Candidate


def serial_protocol_bus_candidates(inputs: BusCandidateInputs) -> tuple[Candidate, ...]:
    """Return serial-specific candidates in the established report order."""
    observed = inputs.observed
    return (
        *serial_signal_candidates(observed),
        *serial_generic_connector_pair_review_candidates(
            observed,
            inputs.reviewed_connector_references,
            inputs.connector_coverage,
        ),
    )
