"""Translate generic connector RS-485 line assignments into review prompts."""

from __future__ import annotations

from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_rs485_generic_connector_candidate_evidence import (
    Rs485GenericConnectorCandidate,
    Rs485GenericConnectorFindingEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .rs485_generic_connector_candidates import rs485_generic_connector_pairs


def rs485_generic_connector_pair_review_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Ask whether generic contacts form a connector requiring RS-485 pinout review."""
    return tuple(
        Rs485GenericConnectorCandidate.from_source_evidence(
            Rs485GenericConnectorFindingEvidence(pair),
            subject=f"{pair.connector_reference}: generic pins match RS-485 A/B bus nets",
            message=(
                "Native assignments place generic connector contacts on both exact A and B nets "
                "of an explicitly identified fitted RS-485 transceiver. Review whether this "
                "connector belongs to that interface and document its exact pinout. This prompt "
                "does not infer connector identity or require any return, shield, or supply "
                "contacts to be common; it does not establish off-board wiring or PCB copper."
            ),
        )
        for pair in rs485_generic_connector_pairs(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
