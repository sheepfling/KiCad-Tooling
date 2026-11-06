"""Coordinate SPI peer, bias, connector, and signal candidates."""

from __future__ import annotations

from .design_lint_bus_inputs import BusCandidateInputs
from .design_lint_spi_candidates import spi_bias_candidates, spi_peer_reference_candidates
from .design_lint_spi_generic_connector_candidates import (
    generic_spi_connector_triad_review_candidates,
)
from .design_lint_spi_signal_candidates import spi_signal_candidates
from .design_lint_types import Candidate


def spi_protocol_bus_candidates(inputs: BusCandidateInputs) -> tuple[Candidate, ...]:
    """Return SPI candidates in the established report order."""
    observed = inputs.observed
    return (
        *spi_peer_reference_candidates(
            observed,
            inputs.spi_peer_reference_scan,
            inputs.component_peer_findings,
        ),
        *spi_bias_candidates(observed, inputs.spi_roster),
        *generic_spi_connector_triad_review_candidates(
            observed,
            inputs.reviewed_connector_references,
            inputs.connector_coverage,
        ),
        *spi_signal_candidates(observed),
    )
