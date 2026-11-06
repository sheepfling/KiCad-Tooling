"""Translate generic connector CAN line assignments into review candidates."""

from __future__ import annotations

from .can_generic_connector_candidates import generic_can_connector_pairs
from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_can_generic_connector_candidate_evidence import (
    CanGenericConnectorCandidate,
    CanGenericConnectorFindingEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract


def generic_can_connector_pair_review_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Request explicit connector-pinout review for generic CAN line contacts."""
    return tuple(
        CanGenericConnectorCandidate.from_source_evidence(
            CanGenericConnectorFindingEvidence(pair),
            subject=f"{pair.connector_reference}: generic pins match CANH/CANL bus nets",
            message=(
                "Native assignments place generic connector contacts on both exact CANH and CANL "
                "nets of a recognized fitted IC endpoint. Review whether the connector is part "
                "of this CAN interface and document its exact pinout. This prompt does not infer "
                "connector identity, require signal or return pins to be common, establish bus "
                "termination placement, prove PCB copper, or establish off-board wiring."
            ),
        )
        for pair in generic_can_connector_pairs(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
