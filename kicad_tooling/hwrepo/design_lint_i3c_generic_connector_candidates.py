"""Translate generic connector I3C pairs into review candidates."""

from __future__ import annotations

from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_i3c_generic_connector_candidate_evidence import (
    I3cGenericConnectorCandidate,
    I3cGenericConnectorFindingEvidence,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .i3c_generic_connector_candidates import generic_i3c_connector_pairs
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "bus.i3c_generic_connector_pair_review"


def generic_i3c_connector_pair_review_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Request explicit connector-pinout review for generic I3C contacts."""
    return tuple(
        I3cGenericConnectorCandidate.from_source_evidence(
            I3cGenericConnectorFindingEvidence(pair),
            subject=f"{pair.connector_reference}: generic pins match I3C SDA/SCL bus nets",
            message=(
                "Native U/IC pin functions identify these exact nets as an I3C SDA/SCL pair, "
                "and generic contacts on this connector are assigned to both nets. Review "
                "whether the connector belongs to this I3C interface and document its exact "
                "pinout. This prompt does not infer connector identity, require common grounds "
                "or power, or prove PCB copper or off-board wiring."
            ),
        )
        for pair in generic_i3c_connector_pairs(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
