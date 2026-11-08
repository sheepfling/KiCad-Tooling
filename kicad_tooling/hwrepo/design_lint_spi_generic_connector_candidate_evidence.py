"""Source projection for generic connector SPI role-triad review prompts."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_contact_evidence import format_other_connector_contacts
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .spi_generic_connector_models import SpiGenericConnectorTriad

SPI_GENERIC_CONNECTOR_RULE_ID: DesignLintRuleId = "bus.spi_generic_connector_triad_review"
_ROLE_LABELS = {
    "clock": "clock",
    "data_input": "controller-to-peripheral data",
    "data_output": "peripheral-to-controller data",
}


@dataclass(frozen=True, slots=True)
class SpiGenericConnectorFindingEvidence:
    """One generic connector assignment and the exact recognized SPI endpoints."""

    triad: SpiGenericConnectorTriad


def project_spi_generic_connector_evidence(
    source: SpiGenericConnectorFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project connector pins, exact nets, and native endpoint role assignments."""
    triad = source.triad
    evidence: dict[str, tuple[str, ...]] = {
        "connector": (triad.connector_reference,),
        "connector_native_pin_count": (str(triad.connector_pin_count),),
    }
    for role in ("clock", "data_input", "data_output"):
        label = _ROLE_LABELS[role]
        evidence[f"{label}_net"] = (triad.role_nets[role],)
        evidence[f"{label}_generic_connector_pins"] = triad.role_connector_pins[role]
        evidence[f"{label}_generic_pin_functions"] = triad.role_connector_functions[role]
    evidence["other_connector_contacts"] = format_other_connector_contacts(
        triad.other_connector_contacts
    )
    evidence["SPI_endpoint_triads"] = tuple(
        f"{item.reference}:{item.channel}:clock={item.clock_pin}/{item.clock_net};"
        f"data_input={item.data_input_pin}/{item.data_input_net};"
        f"data_output={item.data_output_pin}/{item.data_output_net}"
        for item in triad.endpoint_triads
    )
    evidence["connector_map_state"] = (
        "no source-matched SPI role map covers every generic triad contact",
    )
    return CandidateEvidenceProjection(rule_id=SPI_GENERIC_CONNECTOR_RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class SpiGenericConnectorCandidate(Candidate):
    """Review prompt bound to one generic connector/SPI pin assignment."""

    source_evidence: SpiGenericConnectorFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SpiGenericConnectorFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> SpiGenericConnectorCandidate:
        projection = project_spi_generic_connector_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_spi_generic_connector_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("SPI generic-connector evidence must match its source projection")
