"""Source projection for generic USB connector coverage review prompts."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .usb_peer_generic_connector_models import UsbGenericConnectorDataPair

USB_GENERIC_CONNECTOR_RULE_ID: DesignLintRuleId = "bus.usb_generic_connector_phy_pair_review"


@dataclass(frozen=True, slots=True)
class UsbGenericConnectorFindingEvidence:
    """One generic connector assignment and the exact authored-map input."""

    pair: UsbGenericConnectorDataPair
    data_path: UsbDataPathCandidateInputs


def project_usb_generic_connector_evidence(
    source: UsbGenericConnectorFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project native pins, nets, and optional map digest into stable report fields."""
    pair = source.pair
    evidence = {
        "connector": (pair.connector_reference,),
        "PHY": (pair.phy_reference,),
        "USB_D+_PHY_net": (pair.positive_net,),
        "USB_D+_generic_connector_pins": pair.positive_pins,
        "USB_D+_generic_pin_functions": pair.positive_functions,
        "USB_D-_PHY_net": (pair.negative_net,),
        "USB_D-_generic_connector_pins": pair.negative_pins,
        "USB_D-_generic_pin_functions": pair.negative_functions,
        "connector_native_pin_count": (str(pair.connector_pin_count),),
        "USB_data_map_state": ("no map matches this connector/PHY port group",),
    }
    if pair.port_group is not None:
        evidence["USB_port_group"] = (pair.port_group,)
    if source.data_path.map_sha256 is not None:
        evidence["USB_data_map_sha256"] = (source.data_path.map_sha256,)
    return CandidateEvidenceProjection(
        rule_id=USB_GENERIC_CONNECTOR_RULE_ID,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class UsbGenericConnectorCandidate(Candidate):
    """Review prompt bound to one generic connector/PHY pin assignment."""

    source_evidence: UsbGenericConnectorFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UsbGenericConnectorFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> UsbGenericConnectorCandidate:
        projection = project_usb_generic_connector_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_usb_generic_connector_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("USB generic-connector evidence must match its source projection")
