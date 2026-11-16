"""Source projection for USB series-resistor value comparison findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .resistor_paths import resistance_ohms
from .usb_peer_reference_types import UsbPeerDataLink, UsbPeerReferencePathCoverage

USB_UNMAPPED_SERIES_RESISTOR_VALUE_RULE_ID: DesignLintRuleId = (
    "bus.usb_unmapped_series_resistor_value_mismatch"
)


@dataclass(frozen=True, slots=True)
class UsbUnmappedSeriesResistorValueFindingEvidence:
    """One exact endpoint path and the source map used to scope its coverage."""

    path: UsbPeerReferencePathCoverage
    data_path: UsbDataPathCandidateInputs


def _line_description(
    link: UsbPeerDataLink,
    *,
    positive: bool,
) -> tuple[str, ...]:
    resistor = link.positive_series_resistor if positive else link.negative_series_resistor
    if resistor is None:
        raise ValueError("USB value-mismatch evidence requires a resistor on both data lines")
    resistance = resistance_ohms(resistor.value)
    if resistance is None:
        raise ValueError("USB value-mismatch evidence requires parseable resistor values")
    connector_pin = link.connector_positive_pin if positive else link.connector_negative_pin
    connector_net = link.connector_positive_net if positive else link.connector_negative_net
    phy_pin = link.phy_positive_pin if positive else link.phy_negative_pin
    phy_net = link.phy_positive_net if positive else link.phy_negative_net
    return (
        (
            f"{resistor.reference} {resistor.value} {resistor.symbol} {resistor.footprint} "
            f"({resistance:g} Ω): {connector_pin} on {connector_net} -> "
            f"{phy_pin} on {phy_net}"
        ),
    )


def project_usb_unmapped_series_resistor_value_evidence(
    source: UsbUnmappedSeriesResistorValueFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project exact component values and both source-bound paths deterministically."""
    link = source.path.data_link
    positive = link.positive_series_resistor
    negative = link.negative_series_resistor
    positive_ohms = None if positive is None else resistance_ohms(positive.value)
    negative_ohms = None if negative is None else resistance_ohms(negative.value)
    if (
        positive is None
        or negative is None
        or positive_ohms is None
        or negative_ohms is None
        or positive_ohms == negative_ohms
    ):
        raise ValueError("USB series-resistor value evidence must contain a parsed mismatch")
    evidence = {
        "connector": (source.path.connector_reference,),
        "PHY": (source.path.phy_reference,),
        "USB_D+_series_resistor": _line_description(link, positive=True),
        "USB_D-_series_resistor": _line_description(link, positive=False),
        "USB_D+_nominal_resistance_ohms": (f"{positive_ohms:g}",),
        "USB_D-_nominal_resistance_ohms": (f"{negative_ohms:g}",),
        "USB_value_comparison": ("different parsed nominal resistance values",),
        "USB_data_map_state": ("no current map matches this connector/PHY port group",),
    }
    if link.port_group is not None:
        evidence["USB_port_group"] = (link.port_group,)
    if source.data_path.map_sha256 is not None:
        evidence["USB_data_path_map_sha256"] = (source.data_path.map_sha256,)
    return CandidateEvidenceProjection(
        rule_id=USB_UNMAPPED_SERIES_RESISTOR_VALUE_RULE_ID,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class UsbUnmappedSeriesResistorValueCandidate(Candidate):
    """Review prompt validated against its exact typed USB path evidence."""

    source_evidence: UsbUnmappedSeriesResistorValueFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UsbUnmappedSeriesResistorValueFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> UsbUnmappedSeriesResistorValueCandidate:
        projection = project_usb_unmapped_series_resistor_value_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_usb_unmapped_series_resistor_value_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("USB series-resistor evidence must match its typed source projection")
