"""Source projection for generic JTAG connector review prompts."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .jtag_generic_connector_models import JtagGenericConnector

JTAG_GENERIC_CONNECTOR_RULE_ID: DesignLintRuleId = "bus.jtag_generic_connector_pair_review"


@dataclass(frozen=True, slots=True)
class JtagGenericConnectorFindingEvidence:
    """One generic connector matched to native IC TCK/TMS signal nets."""

    pair: JtagGenericConnector


def project_jtag_generic_connector_evidence(
    source: JtagGenericConnectorFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project exact endpoint pins, net assignments, and connector contacts."""
    pair = source.pair
    return CandidateEvidenceProjection(
        rule_id=JTAG_GENERIC_CONNECTOR_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": (str(pair.connector_pin_count),),
            "TCK_net": (pair.tck_net,),
            "TCK_generic_connector_pins": pair.tck_connector_pins,
            "TCK_generic_pin_functions": pair.tck_connector_functions,
            "TMS_net": (pair.tms_net,),
            "TMS_generic_connector_pins": pair.tms_connector_pins,
            "TMS_generic_pin_functions": pair.tms_connector_functions,
            "jtag_endpoint_pairs": tuple(
                f"{item.reference}:{item.tck_pin}={item.tck_function}/"
                f"{item.tck_net};{item.tms_pin}={item.tms_function}/"
                f"{item.tms_net}"
                for item in pair.endpoints
            ),
            "connector_map_state": (
                "no source-matched JTAG connector pin map covers both exact roles",
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class JtagGenericConnectorCandidate(Candidate):
    """Review prompt bound to exact connector and IC TCK/TMS evidence."""

    source_evidence: JtagGenericConnectorFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: JtagGenericConnectorFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> JtagGenericConnectorCandidate:
        projection = project_jtag_generic_connector_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_jtag_generic_connector_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("JTAG evidence must match its source projection")
