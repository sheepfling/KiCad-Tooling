"""Source projection for generic connector USB-C CC pair review prompts."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .usb_c_generic_connector import UsbCGenericConnectorPair
from .usb_c_ports import UsbCPortRosterContext

USB_C_GENERIC_CONNECTOR_RULE_ID: DesignLintRuleId = "bus.usb_c_generic_connector_cc_pair_review"


@dataclass(frozen=True, slots=True)
class UsbCGenericConnectorFindingEvidence:
    """One direct generic connector/controller match and its map context."""

    pair: UsbCGenericConnectorPair
    roster: UsbCPortRosterContext


def project_usb_c_generic_connector_evidence(
    source: UsbCGenericConnectorFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the exact endpoint roles, generic contacts, and optional map digest."""
    pair = source.pair
    evidence = {
        "connector": (pair.connector_reference,),
        "USB_C_controller": (pair.controller_reference,),
        "USB_C_CC1_controller_pin": (pair.controller_cc1_pin,),
        "USB_C_CC1_controller_function": (pair.controller_cc1_function,),
        "USB_C_CC1_net": (pair.cc1_net,),
        "USB_C_CC1_generic_connector_pins": pair.connector_cc1_pins,
        "USB_C_CC1_generic_pin_functions": pair.connector_cc1_functions,
        "USB_C_CC2_controller_pin": (pair.controller_cc2_pin,),
        "USB_C_CC2_controller_function": (pair.controller_cc2_function,),
        "USB_C_CC2_net": (pair.cc2_net,),
        "USB_C_CC2_generic_connector_pins": pair.connector_cc2_pins,
        "USB_C_CC2_generic_pin_functions": pair.connector_cc2_functions,
        "connector_native_pin_count": (str(pair.connector_pin_count),),
        "USB_C_port_map_state": ("no USB-C port map names this connector",),
    }
    if source.roster.source_sha256 is not None:
        evidence["USB_C_port_map_sha256"] = (source.roster.source_sha256,)
    return CandidateEvidenceProjection(
        rule_id=USB_C_GENERIC_CONNECTOR_RULE_ID,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class UsbCGenericConnectorCandidate(Candidate):
    """Review prompt bound to one generic connector/controller pin assignment."""

    source_evidence: UsbCGenericConnectorFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UsbCGenericConnectorFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> UsbCGenericConnectorCandidate:
        projection = project_usb_c_generic_connector_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_usb_c_generic_connector_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("USB-C generic-connector evidence must match its source projection")
