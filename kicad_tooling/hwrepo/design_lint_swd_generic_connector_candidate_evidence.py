"""Source projection for generic SWD debug-connector review prompts."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .swd_generic_connector_models import SwdGenericConnector

SWD_GENERIC_CONNECTOR_RULE_ID: DesignLintRuleId = "bus.swd_generic_connector_pair_review"


@dataclass(frozen=True, slots=True)
class SwdGenericConnectorFindingEvidence:
    """One generic connector mapped by native assignment to an SWD pair."""

    pair: SwdGenericConnector


def project_swd_generic_connector_evidence(
    source: SwdGenericConnectorFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project exact SWD endpoint pins, nets, and generic connector contacts."""
    pair = source.pair
    return CandidateEvidenceProjection(
        rule_id=SWD_GENERIC_CONNECTOR_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": (str(pair.connector_pin_count),),
            "SWDIO_net": (pair.swdio_net,),
            "SWDIO_generic_connector_pins": pair.swdio_connector_pins,
            "SWDIO_generic_pin_functions": pair.swdio_connector_functions,
            "SWCLK_net": (pair.swclk_net,),
            "SWCLK_generic_connector_pins": pair.swclk_connector_pins,
            "SWCLK_generic_pin_functions": pair.swclk_connector_functions,
            "swd_endpoint_pairs": tuple(
                f"{item.reference}:{item.swdio_pin}={item.swdio_function}/"
                f"{item.swdio_net};{item.swclk_pin}={item.swclk_function}/"
                f"{item.swclk_net}"
                for item in pair.endpoints
            ),
            "connector_map_state": (
                "no source-matched SWD connector pin map covers both exact roles",
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class SwdGenericConnectorCandidate(Candidate):
    """Review prompt bound to exact connector and MCU SWD evidence."""

    source_evidence: SwdGenericConnectorFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SwdGenericConnectorFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> SwdGenericConnectorCandidate:
        projection = project_swd_generic_connector_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_swd_generic_connector_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("SWD evidence must match its source projection")
