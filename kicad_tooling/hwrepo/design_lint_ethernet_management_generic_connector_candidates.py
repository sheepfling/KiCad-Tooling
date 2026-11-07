"""Translate Ethernet MDC/MDIO generic-connector observations into reviews."""

from __future__ import annotations

from .bus_ethernet_management_generic_connector import (
    generic_ethernet_management_connector_pairs,
)
from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_ethernet_management_generic_connector_candidate_evidence import (
    EthernetManagementGenericConnectorCandidate,
    EthernetManagementGenericConnectorFindingEvidence,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "bus.ethernet_management_generic_connector_pair_review"


def ethernet_management_generic_connector_pair_review_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Ask whether generic contacts on Ethernet MDC/MDIO nets need a pinout."""
    return tuple(
        EthernetManagementGenericConnectorCandidate.from_source_evidence(
            EthernetManagementGenericConnectorFindingEvidence(pair),
            subject=(
                f"{pair.connector_reference}: generic pins match Ethernet MDC/MDIO management nets"
            ),
            message=(
                "Native assignments place generic connector contacts on both exact MDC and MDIO "
                "nets of recognized fitted IC endpoint(s). Review whether the connector belongs "
                "to this management interface and document its exact pinout. This prompt does "
                "not identify the connector's purpose, establish an Ethernet port topology, "
                "prove PCB copper, or determine required return, power, or shield connections."
            ),
        )
        for pair in generic_ethernet_management_connector_pairs(
            observed, reviewed_connector_references, connector_coverage
        )
    )
