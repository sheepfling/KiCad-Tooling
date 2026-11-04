"""Typed source projections for USB data pin/net polarity candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .bus_signal_pairs import usb_data_function_identity
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

UsbDataPolaritySide = Literal["positive", "negative"]
USB_DATA_POLARITY_RULE_ID: DesignLintRuleId = "bus.usb_data_polarity_label_mismatch"


def usb_data_polarity_side(value: str) -> UsbDataPolaritySide:
    """Narrow the shared alias helper's string result to its reviewed side values."""
    if value == "positive":
        return "positive"
    if value == "negative":
        return "negative"
    raise ValueError(f"Unsupported USB data polarity side: {value}")


@dataclass(frozen=True, slots=True)
class UsbDataPolarityFindingEvidence:
    """One exact pin-to-net polarity conflict from the normalized netlist."""

    observed: NetlistContract
    pin: str
    function: str
    pin_side: UsbDataPolaritySide
    net: str
    net_side: UsbDataPolaritySide
    port_group: str | None

    def __post_init__(self) -> None:
        if self.observed.pin_functions.get(self.pin) != self.function:
            raise ValueError("USB polarity function must match its source netlist")
        if self.pin not in self.observed.nets.get(self.net, ()):
            raise ValueError("USB polarity net must contain its source pin")
        if usb_data_function_identity(self.function) != (self.port_group, self.pin_side):
            raise ValueError("USB polarity pin identity must match its source function")
        if usb_data_function_identity(self.net) != (self.port_group, self.net_side):
            raise ValueError("USB polarity net identity must match its source label")
        if self.pin_side == self.net_side:
            raise ValueError("USB polarity source must describe opposite pin and net sides")


def project_usb_data_polarity_evidence(
    source: UsbDataPolarityFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project a typed polarity conflict into its stable report fields."""
    return CandidateEvidenceProjection(
        rule_id=USB_DATA_POLARITY_RULE_ID,
        evidence={
            "pin": (source.pin,),
            "pin_function": (source.function,),
            "pin_side": (source.pin_side,),
            "net": (source.net,),
            "net_side": (source.net_side,),
            "port_group": (source.port_group or "unindexed",),
        },
    )


@dataclass(frozen=True, slots=True)
class UsbDataPolarityCandidate(Candidate):
    """USB polarity prompt retaining its exact source netlist and conflict."""

    source_evidence: UsbDataPolarityFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UsbDataPolarityFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> UsbDataPolarityCandidate:
        projection = project_usb_data_polarity_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_usb_data_polarity_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("USB polarity fields must match their typed source projection")
