"""Translate generic SWD connector observations into review candidates."""

from __future__ import annotations

from .bus_swd_generic_connector import generic_swd_connector_pairs
from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_swd_generic_connector_candidate_evidence import (
    SwdGenericConnectorCandidate,
    SwdGenericConnectorFindingEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "bus.swd_generic_connector_pair_review"


def swd_generic_connector_pair_review_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Ask whether generic contacts on an MCU SWD pair need a reviewed pinout."""
    return tuple(
        SwdGenericConnectorCandidate.from_source_evidence(
            SwdGenericConnectorFindingEvidence(pair),
            subject=f"{pair.connector_reference}: generic pins match native SWDIO/SWCLK nets",
            message=(
                "Native assignments place generic connector contacts on both exact SWDIO and "
                "SWCLK nets of recognized fitted IC endpoint(s). Review whether the connector "
                "belongs to an SWD debug interface and document its exact pinout. This prompt "
                "does not identify the connector's purpose, decide debug-access policy or "
                "reference/power requirements, or prove PCB copper continuity."
            ),
        )
        for pair in generic_swd_connector_pairs(
            observed, reviewed_connector_references, connector_coverage
        )
    )
