"""Review two-contact I2C connectors with no identified reference return."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_return_pins import connector_pin_group_has_return_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .i2c_generic_connector_candidates import generic_i2c_connector_pairs
from .i2c_generic_connector_models import I2cGenericConnectorPair
from .netlist_contract_models import NetlistContract

I2C_CONNECTOR_RETURN_RULE_ID: DesignLintRuleId = "connector.i2c_pair_without_return_review"


@dataclass(frozen=True, slots=True)
class I2cConnectorReturnEvidence:
    """A complete two-pin connector carrying a native I2C pair."""

    pair: I2cGenericConnectorPair


def _project_evidence(source: I2cConnectorReturnEvidence) -> CandidateEvidenceProjection:
    pair = source.pair
    return CandidateEvidenceProjection(
        rule_id=I2C_CONNECTOR_RETURN_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": (str(pair.connector_pin_count),),
            "connected_contact_count": ("2",),
            "SDA_net": (pair.sda_net,),
            "SDA_generic_connector_pins": pair.sda_connector_pins,
            "SCL_net": (pair.scl_net,),
            "SCL_generic_connector_pins": pair.scl_connector_pins,
            "I2C_endpoint_pairs": tuple(
                f"{item.reference}:{item.sda_pin}=SDA/{item.sda_net};"
                f"{item.scl_pin}=SCL/{item.scl_net}"
                for item in pair.endpoint_pairs
            ),
            "identified_connector_return_role": (),
        },
    )


@dataclass(frozen=True, slots=True)
class I2cConnectorReturnCandidate(Candidate):
    """Source-bound review prompt for a two-pin I2C connector's reference."""

    source_evidence: I2cConnectorReturnEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: I2cConnectorReturnEvidence,
    ) -> I2cConnectorReturnCandidate:
        projection = _project_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.pair.connector_reference}: two-pin I2C connector "
                "has no identified reference return"
            ),
            message=(
                "Native U/IC pin functions identify this complete two-pin connector as a "
                "generic I2C SDA/SCL pair, and no connector contact function or current, "
                "source-matched pin map identifies a return. Review whether the signal "
                "reference is provided elsewhere, the interface is intentionally isolated, "
                "or the connector pinout needs a return contact. This prompt does not require "
                "connection to board ground or establish external wiring or PCB copper."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = _project_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("I2C connector return evidence must match its source projection")


def i2c_connector_missing_return_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Prompt on exact two-pin generic I2C connectors without a return role.

    This asks for a reference and pinout review only. It does not require a
    local ground or infer external wiring, isolation, or PCB continuity.
    """
    mapped = source_matched_connector_pin_evidence(observed, connector_coverage)
    found: list[Candidate] = []
    for pair in generic_i2c_connector_pairs(
        observed,
        reviewed_connector_references,
        connector_coverage,
    ):
        if (
            pair.connector_pin_count != 2
            or len(pair.sda_connector_pins) != 1
            or len(pair.scl_connector_pins) != 1
        ):
            continue
        connector_pins = (*pair.sda_connector_pins, *pair.scl_connector_pins)
        if connector_pin_group_has_return_role(
            connector_pins,
            observed.pin_functions,
            mapped,
        ):
            continue
        found.append(
            I2cConnectorReturnCandidate.from_source_evidence(I2cConnectorReturnEvidence(pair))
        )

    return tuple(
        sorted(
            found,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(sorted((key, value) for key, value in item.evidence.items())),
            ),
        )
    )
