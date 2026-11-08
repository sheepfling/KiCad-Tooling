"""Source projection for generic connector I2C pair review prompts."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_contact_evidence import format_other_connector_contacts
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .i2c_generic_connector_models import I2cGenericConnectorPair

I2C_GENERIC_CONNECTOR_RULE_ID: DesignLintRuleId = "bus.i2c_generic_connector_pair_review"


@dataclass(frozen=True, slots=True)
class I2cGenericConnectorFindingEvidence:
    """One generic connector assignment and the exact recognized I2C endpoints."""

    pair: I2cGenericConnectorPair


def project_i2c_generic_connector_evidence(
    source: I2cGenericConnectorFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project connector pins, exact SDA/SCL nets, and endpoint assignments."""
    pair = source.pair
    return CandidateEvidenceProjection(
        rule_id=I2C_GENERIC_CONNECTOR_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": (str(pair.connector_pin_count),),
            "SDA_net": (pair.sda_net,),
            "SDA_generic_connector_pins": pair.sda_connector_pins,
            "SDA_generic_pin_functions": pair.sda_connector_functions,
            "SCL_net": (pair.scl_net,),
            "SCL_generic_connector_pins": pair.scl_connector_pins,
            "SCL_generic_pin_functions": pair.scl_connector_functions,
            "I2C_endpoint_pairs": tuple(
                f"{item.reference}:{item.sda_pin}=SDA/{item.sda_net};"
                f"{item.scl_pin}=SCL/{item.scl_net}"
                for item in pair.endpoint_pairs
            ),
            "other_connector_contacts": format_other_connector_contacts(
                pair.other_connector_contacts
            ),
            "connector_map_state": (
                "no source-matched SDA/SCL connector pin map covers this pair",
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class I2cGenericConnectorCandidate(Candidate):
    """Review prompt bound to one generic connector/I2C pin assignment."""

    source_evidence: I2cGenericConnectorFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: I2cGenericConnectorFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> I2cGenericConnectorCandidate:
        projection = project_i2c_generic_connector_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_i2c_generic_connector_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("I2C generic-connector evidence must match its source projection")
