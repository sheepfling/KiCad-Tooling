"""Translate generic connector SPI role triads into review candidates."""

from __future__ import annotations

from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_spi_generic_connector_candidate_evidence import (
    SpiGenericConnectorCandidate,
    SpiGenericConnectorFindingEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .spi_generic_connector_candidates import generic_spi_connector_triads


def generic_spi_connector_triad_review_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Request review when generic connector contacts span an exact SPI triad."""
    return tuple(
        SpiGenericConnectorCandidate.from_source_evidence(
            SpiGenericConnectorFindingEvidence(triad),
            subject=f"{triad.connector_reference}: generic pins match SPI clock and both data roles",
            message=(
                "Native assignments place generic connector contacts on the exact clock, "
                "controller-to-peripheral data, and peripheral-to-controller data nets of a "
                "recognized fitted IC endpoint. Review whether this connector is part of that "
                "SPI interface and document its pinout. This prompt does not infer connector or "
                "device identity, chip-select requirements, return or power requirements, "
                "off-board wiring, or PCB copper continuity."
            ),
        )
        for triad in generic_spi_connector_triads(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
