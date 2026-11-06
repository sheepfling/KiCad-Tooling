"""Source projection for generic connector CAN-pair review prompts."""

from __future__ import annotations

from dataclasses import dataclass

from .can_generic_connector_models import CanGenericConnectorPair
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection

CAN_GENERIC_CONNECTOR_RULE_ID: DesignLintRuleId = "bus.can_generic_connector_pair_review"


@dataclass(frozen=True, slots=True)
class CanGenericConnectorFindingEvidence:
    """One generic connector assignment and the exact recognized CAN endpoints."""

    pair: CanGenericConnectorPair


def project_can_generic_connector_evidence(
    source: CanGenericConnectorFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project connector pins, exact line nets, and CAN endpoint assignments."""
    pair = source.pair
    return CandidateEvidenceProjection(
        rule_id=CAN_GENERIC_CONNECTOR_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": (str(pair.connector_pin_count),),
            "CANH_net": (pair.canh_net,),
            "CANH_generic_connector_pins": pair.canh_connector_pins,
            "CANH_generic_pin_functions": pair.canh_connector_functions,
            "CANL_net": (pair.canl_net,),
            "CANL_generic_connector_pins": pair.canl_connector_pins,
            "CANL_generic_pin_functions": pair.canl_connector_functions,
            "CAN_endpoint_pairs": tuple(
                f"{item.reference}:{item.canh_pin}=CANH/{item.canh_net};"
                f"{item.canl_pin}=CANL/{item.canl_net}"
                for item in pair.endpoint_pairs
            ),
            "connector_map_state": (
                "no source-matched CANH/CANL connector pin map covers this pair",
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class CanGenericConnectorCandidate(Candidate):
    """Review prompt bound to one generic connector/CAN pin assignment."""

    source_evidence: CanGenericConnectorFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: CanGenericConnectorFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> CanGenericConnectorCandidate:
        projection = project_can_generic_connector_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_can_generic_connector_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("CAN generic-connector evidence must match its source projection")
