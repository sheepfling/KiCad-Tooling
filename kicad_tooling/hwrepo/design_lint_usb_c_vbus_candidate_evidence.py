"""Typed report projection for USB-C VBUS capacitance review candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .usb_c_vbus_review import UsbCVbusCapacitanceGap

_USB_C_VBUS_CAPACITANCE_REVIEW: DesignLintRuleId = "bus.usb_c_vbus_capacitance_review"


@dataclass(frozen=True, slots=True)
class UsbCVbusCapacitanceReviewEvidence:
    """Exact port contact assignments and capacitor observations for a prompt."""

    gap: UsbCVbusCapacitanceGap


def project_usb_c_vbus_capacitance_evidence(
    source: UsbCVbusCapacitanceReviewEvidence,
) -> CandidateEvidenceProjection:
    gap = source.gap
    evidence: dict[str, tuple[str, ...]] = {
        "connector": (gap.connector,),
        "CC1_pins": gap.cc1_pins,
        "CC2_pins": gap.cc2_pins,
        "VBUS_pin_assignments": tuple(f"{pin}={net}" for pin, net in gap.vbus_pin_assignments),
        "return_pin_assignments": tuple(f"{pin}={net}" for pin, net in gap.return_pin_assignments),
        "VBUS_net": (gap.vbus_net,),
        "return_net": (gap.return_net,),
        "capacitor_touchpoints": gap.capacitor_touchpoints or ("none",),
        "VBUS_capacitance_scope": (gap.review_scope,),
    }
    if gap.electrical_contract_path is not None:
        evidence["electrical_contract_path"] = (gap.electrical_contract_path,)
    if gap.electrical_contract_sha256 is not None:
        evidence["electrical_contract_sha256"] = (gap.electrical_contract_sha256,)
    return CandidateEvidenceProjection(rule_id=_USB_C_VBUS_CAPACITANCE_REVIEW, evidence=evidence)


@dataclass(frozen=True, slots=True)
class UsbCVbusCapacitanceReviewCandidate(Candidate):
    """Review prompt retaining its native port/capacitor evidence."""

    source_evidence: UsbCVbusCapacitanceReviewEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UsbCVbusCapacitanceReviewEvidence,
        *,
        subject: str,
        message: str,
    ) -> UsbCVbusCapacitanceReviewCandidate:
        projection = project_usb_c_vbus_capacitance_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_usb_c_vbus_capacitance_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("USB-C VBUS fields must match their typed source projection")
