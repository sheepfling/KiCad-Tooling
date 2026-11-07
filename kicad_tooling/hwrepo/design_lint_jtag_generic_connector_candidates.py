"""Translate generic JTAG connector observations into review candidates."""

from __future__ import annotations

from .bus_jtag_generic_connector import generic_jtag_connector_pairs
from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_jtag_generic_connector_candidate_evidence import (
    JtagGenericConnectorCandidate,
    JtagGenericConnectorFindingEvidence,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "bus.jtag_generic_connector_pair_review"


def jtag_generic_connector_pair_review_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Ask whether generic contacts on an IC TCK/TMS pair need a reviewed pinout."""
    return tuple(
        JtagGenericConnectorCandidate.from_source_evidence(
            JtagGenericConnectorFindingEvidence(pair),
            subject=f"{pair.connector_reference}: generic pins match native JTAG TCK/TMS nets",
            message=(
                "Native assignments place generic connector contacts on both exact TCK and TMS "
                "nets of recognized fitted IC endpoint(s). Review whether the connector belongs "
                "to a JTAG interface and document its pinout, including any omitted signal, "
                "reference, or power contacts required by the approved design. This prompt does "
                "not establish connector purpose, require every JTAG signal or ground to be "
                "exposed, or prove PCB copper continuity."
            ),
        )
        for pair in generic_jtag_connector_pairs(
            observed, reviewed_connector_references, connector_coverage
        )
    )
