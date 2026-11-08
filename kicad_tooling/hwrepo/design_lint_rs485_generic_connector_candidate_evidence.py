"""Source projection for generic connector RS-485 line-pair review."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_contact_evidence import format_other_connector_contacts
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .rs485_generic_connector_models import Rs485GenericConnectorPair

RS485_GENERIC_CONNECTOR_RULE_ID: DesignLintRuleId = "bus.rs485_generic_connector_pair_review"


@dataclass(frozen=True, slots=True)
class Rs485GenericConnectorFindingEvidence:
    """One generic connector assignment and its exact recognized endpoints."""

    pair: Rs485GenericConnectorPair


def project_rs485_generic_connector_evidence(
    source: Rs485GenericConnectorFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project connector contacts, line nets, and transceiver pin assignments."""
    pair = source.pair
    return CandidateEvidenceProjection(
        rule_id=RS485_GENERIC_CONNECTOR_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": (str(pair.connector_pin_count),),
            "A_net": (pair.a_net,),
            "A_generic_connector_pins": pair.a_connector_pins,
            "A_generic_pin_functions": pair.a_connector_functions,
            "B_net": (pair.b_net,),
            "B_generic_connector_pins": pair.b_connector_pins,
            "B_generic_pin_functions": pair.b_connector_functions,
            "RS485_endpoint_pairs": tuple(
                f"{item.reference}:A={item.a_pin}/{item.a_net};B={item.b_pin}/{item.b_net}"
                for item in pair.endpoint_pairs
            ),
            "other_connector_contacts": format_other_connector_contacts(
                pair.other_connector_contacts
            ),
            "connector_map_state": (
                "no source-matched RS-485 A/B connector pin map covers this pair",
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class Rs485GenericConnectorCandidate(Candidate):
    """Review prompt bound to one generic connector/RS-485 assignment."""

    source_evidence: Rs485GenericConnectorFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: Rs485GenericConnectorFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> Rs485GenericConnectorCandidate:
        projection = project_rs485_generic_connector_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_rs485_generic_connector_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("RS-485 generic-connector evidence must match its source projection")
