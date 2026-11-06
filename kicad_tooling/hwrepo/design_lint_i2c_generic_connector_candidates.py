"""Translate generic connector I2C line assignments into review candidates."""

from __future__ import annotations

from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_i2c_generic_connector_candidate_evidence import (
    I2cGenericConnectorCandidate,
    I2cGenericConnectorFindingEvidence,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .i2c_generic_connector_candidates import generic_i2c_connector_pairs
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "bus.i2c_generic_connector_pair_review"


def generic_i2c_connector_pair_review_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Request explicit connector-pinout review for generic I2C line contacts."""
    return tuple(
        I2cGenericConnectorCandidate.from_source_evidence(
            I2cGenericConnectorFindingEvidence(pair),
            subject=f"{pair.connector_reference}: generic pins match SDA/SCL bus nets",
            message=(
                "Native assignments place generic connector contacts on both exact SDA and SCL "
                "nets of a recognized fitted IC endpoint. Review whether the connector belongs "
                "to this I2C interface and document its exact pinout. This prompt does not infer "
                "connector identity, require common grounds or power, establish bus membership "
                "beyond these net assignments, or prove PCB copper or off-board wiring."
            ),
        )
        for pair in generic_i2c_connector_pairs(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
