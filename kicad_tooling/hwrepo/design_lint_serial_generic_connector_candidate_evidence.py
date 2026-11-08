"""Source projection for generic connector UART pair review prompts."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_contact_evidence import format_other_connector_contacts
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .serial_generic_connector_models import SerialGenericConnectorPair

SERIAL_GENERIC_CONNECTOR_RULE_ID: DesignLintRuleId = "bus.serial_generic_connector_pair_review"


@dataclass(frozen=True, slots=True)
class SerialGenericConnectorFindingEvidence:
    """One generic connector assignment and its exact native UART endpoints."""

    pair: SerialGenericConnectorPair


def project_serial_generic_connector_evidence(
    source: SerialGenericConnectorFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project exact TX/RX nets, generic connector contacts, and endpoint pins."""
    pair = source.pair
    return CandidateEvidenceProjection(
        rule_id=SERIAL_GENERIC_CONNECTOR_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": (str(pair.connector_pin_count),),
            "TX_net": (pair.tx_net,),
            "TX_generic_connector_pins": pair.tx_connector_pins,
            "TX_generic_pin_functions": pair.tx_connector_functions,
            "RX_net": (pair.rx_net,),
            "RX_generic_connector_pins": pair.rx_connector_pins,
            "RX_generic_pin_functions": pair.rx_connector_functions,
            "UART_endpoint_pairs": tuple(
                f"{item.reference}:{item.channel}:TX={item.tx_pin}/{item.tx_net};"
                f"RX={item.rx_pin}/{item.rx_net}"
                for item in pair.endpoint_pairs
            ),
            "other_connector_contacts": format_other_connector_contacts(
                pair.other_connector_contacts
            ),
            "connector_map_state": (
                "no source-matched UART role map covers every generic pair contact",
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class SerialGenericConnectorCandidate(Candidate):
    """Review prompt bound to one generic connector/UART pin assignment."""

    source_evidence: SerialGenericConnectorFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SerialGenericConnectorFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> SerialGenericConnectorCandidate:
        projection = project_serial_generic_connector_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_serial_generic_connector_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Serial generic-connector evidence must match its source projection")
