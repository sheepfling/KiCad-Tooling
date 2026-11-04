"""Typed source projections for unmapped USB-C port candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .usb_c_ports import UnmappedUsbCPort, UsbCPortRosterContext


@dataclass(frozen=True, slots=True)
class UsbCPortFindingEvidence:
    """One discovered connector and the roster context used to classify it."""

    port: UnmappedUsbCPort
    roster: UsbCPortRosterContext


_USB_C_UNREVIEWED_PORT: DesignLintRuleId = "bus.usb_c_unreviewed_port"


def project_usb_c_port_evidence(
    source: UsbCPortFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the connector and authored roster source into stable report fields."""
    evidence = {
        "CC1_pins": source.port.cc1_pins,
        "CC2_pins": source.port.cc2_pins,
        "CC_assignments": source.port.signal_assignments,
        "USB_C_roster_state": (source.roster.state,),
    }
    if source.roster.source_path is not None:
        evidence["electrical_contract_path"] = (source.roster.source_path,)
    if source.roster.source_sha256 is not None:
        evidence["electrical_contract_sha256"] = (source.roster.source_sha256,)
    return CandidateEvidenceProjection(rule_id=_USB_C_UNREVIEWED_PORT, evidence=evidence)


@dataclass(frozen=True, slots=True)
class UsbCPortCandidate(Candidate):
    """Coverage prompt retaining the exact connector and roster source records."""

    source_evidence: UsbCPortFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UsbCPortFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> UsbCPortCandidate:
        projection = project_usb_c_port_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_usb_c_port_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("USB-C port fields must match their typed source projection")
