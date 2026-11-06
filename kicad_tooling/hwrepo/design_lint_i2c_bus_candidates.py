"""Coordinate I2C pull-up, peer-reference, and connector candidates."""

from __future__ import annotations

from .design_lint_bus_inputs import BusCandidateInputs
from .design_lint_i2c_candidates import i2c_peer_reference_candidates
from .design_lint_i2c_generic_connector_candidates import (
    generic_i2c_connector_pair_review_candidates,
)
from .design_lint_i2c_pullup_candidates import i2c_pullup_theme_candidates
from .design_lint_types import Candidate


def i2c_protocol_bus_candidates(inputs: BusCandidateInputs) -> tuple[Candidate, ...]:
    """Return I2C-specific candidates in the established report order."""
    observed = inputs.observed
    return (
        *i2c_pullup_theme_candidates(inputs.i2c_pullup),
        *i2c_peer_reference_candidates(
            observed,
            inputs.i2c_peer_reference_scan,
            inputs.component_peer_findings,
        ),
        *generic_i2c_connector_pair_review_candidates(
            observed,
            inputs.reviewed_connector_references,
            inputs.connector_coverage,
        ),
    )
