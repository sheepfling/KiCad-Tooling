"""Source projection for generic connector Ethernet-pair review prompts."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .ethernet_generic_connector_models import EthernetGenericConnectorPair

ETHERNET_GENERIC_CONNECTOR_RULE_ID: DesignLintRuleId = "bus.ethernet_generic_connector_pair_review"


@dataclass(frozen=True, slots=True)
class EthernetGenericConnectorFindingEvidence:
    """One connector assignment and the exact recognized Ethernet endpoints."""

    pair: EthernetGenericConnectorPair


def project_ethernet_generic_connector_evidence(
    source: EthernetGenericConnectorFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project connector contacts, exact pair nets, and native PHY assignments."""
    pair = source.pair
    direction = pair.direction
    return CandidateEvidenceProjection(
        rule_id=ETHERNET_GENERIC_CONNECTOR_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": (str(pair.connector_pin_count),),
            f"Ethernet_{direction}_positive_net": (pair.positive_net,),
            f"Ethernet_{direction}_positive_generic_connector_pins": (pair.positive_connector_pins),
            f"Ethernet_{direction}_positive_generic_pin_functions": (
                pair.positive_connector_functions
            ),
            f"Ethernet_{direction}_negative_net": (pair.negative_net,),
            f"Ethernet_{direction}_negative_generic_connector_pins": (pair.negative_connector_pins),
            f"Ethernet_{direction}_negative_generic_pin_functions": (
                pair.negative_connector_functions
            ),
            "Ethernet_endpoint_pairs": tuple(
                f"{item.reference}:{item.positive_pin}={direction}+/{item.positive_net};"
                f"{item.negative_pin}={direction}-/{item.negative_net}"
                for item in pair.endpoint_pairs
            ),
            "Ethernet_pair_direction": (direction,),
            "connector_map_state": (
                "no source-matched Ethernet pin map covers both exact pair sides",
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class EthernetGenericConnectorCandidate(Candidate):
    """Review prompt bound to one generic connector/Ethernet pin assignment."""

    source_evidence: EthernetGenericConnectorFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: EthernetGenericConnectorFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> EthernetGenericConnectorCandidate:
        projection = project_ethernet_generic_connector_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_ethernet_generic_connector_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Ethernet generic-connector evidence must match its source projection")
