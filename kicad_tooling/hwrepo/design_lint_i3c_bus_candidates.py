"""Coordinate I3C connector review candidates."""

from __future__ import annotations

from .design_lint_bus_inputs import BusCandidateInputs
from .design_lint_i3c_generic_connector_candidates import (
    generic_i3c_connector_pair_review_candidates,
)
from .design_lint_types import Candidate


def i3c_protocol_bus_candidates(inputs: BusCandidateInputs) -> tuple[Candidate, ...]:
    """Return I3C-specific bus candidates in stable protocol order."""
    return generic_i3c_connector_pair_review_candidates(
        inputs.observed,
        inputs.reviewed_connector_references,
        inputs.connector_coverage,
    )
