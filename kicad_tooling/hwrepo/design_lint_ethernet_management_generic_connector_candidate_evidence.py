"""Source projection for Ethernet MDC/MDIO connector review prompts."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_contact_evidence import format_other_connector_contacts
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .ethernet_management_generic_connector_models import EthernetManagementGenericConnector

ETHERNET_MANAGEMENT_GENERIC_CONNECTOR_RULE_ID: DesignLintRuleId = (
    "bus.ethernet_management_generic_connector_pair_review"
)


@dataclass(frozen=True, slots=True)
class EthernetManagementGenericConnectorFindingEvidence:
    """One generic connector mapped by native assignment to MDC/MDIO nets."""

    pair: EthernetManagementGenericConnector


def project_ethernet_management_generic_connector_evidence(
    source: EthernetManagementGenericConnectorFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project exact management pins, nets, connector contacts, and endpoints."""
    pair = source.pair
    return CandidateEvidenceProjection(
        rule_id=ETHERNET_MANAGEMENT_GENERIC_CONNECTOR_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": (str(pair.connector_pin_count),),
            "Ethernet_MDC_net": (pair.mdc_net,),
            "Ethernet_MDC_generic_connector_pins": pair.mdc_connector_pins,
            "Ethernet_MDC_generic_pin_functions": pair.mdc_connector_functions,
            "Ethernet_MDIO_net": (pair.mdio_net,),
            "Ethernet_MDIO_generic_connector_pins": pair.mdio_connector_pins,
            "Ethernet_MDIO_generic_pin_functions": pair.mdio_connector_functions,
            "Ethernet_management_endpoint_pairs": tuple(
                f"{item.reference}:{item.mdc_pin}=MDC/{item.mdc_net};"
                f"{item.mdio_pin}=MDIO/{item.mdio_net}"
                for item in pair.endpoint_pairs
            ),
            "other_connector_contacts": format_other_connector_contacts(
                pair.other_connector_contacts
            ),
            "connector_map_state": (
                "no source-matched MDC/MDIO connector pin map covers both exact roles",
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class EthernetManagementGenericConnectorCandidate(Candidate):
    """Review prompt bound to exact connector and Ethernet-management evidence."""

    source_evidence: EthernetManagementGenericConnectorFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: EthernetManagementGenericConnectorFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> EthernetManagementGenericConnectorCandidate:
        projection = project_ethernet_management_generic_connector_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_ethernet_management_generic_connector_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Ethernet management evidence must match its source projection")
