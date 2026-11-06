"""Translate generic connector Ethernet-pair observations into review candidates."""

from __future__ import annotations

from .bus_ethernet_generic_connector import generic_ethernet_connector_pairs
from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_ethernet_generic_connector_candidate_evidence import (
    EthernetGenericConnectorCandidate,
    EthernetGenericConnectorFindingEvidence,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "bus.ethernet_generic_connector_pair_review"


def ethernet_generic_connector_pair_review_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Ask for connector pinout review when generic pins match a PHY data pair."""
    return tuple(
        EthernetGenericConnectorCandidate.from_source_evidence(
            EthernetGenericConnectorFindingEvidence(pair),
            subject=(
                f"{pair.connector_reference}: generic pins match Ethernet {pair.direction} pair nets"
            ),
            message=(
                f"Native assignments place generic connector contacts on both exact Ethernet "
                f"{pair.direction} pair nets of recognized fitted IC endpoint(s). Review whether "
                "the connector belongs to this interface and document its exact pinout. This "
                "prompt does not identify the connector as Ethernet, prove a PHY-to-port path, "
                "determine whether magnetics or termination are required, establish PCB copper, "
                "or decide how power, return, or shield contacts should be connected."
            ),
        )
        for pair in generic_ethernet_connector_pairs(
            observed, reviewed_connector_references, connector_coverage
        )
    )
