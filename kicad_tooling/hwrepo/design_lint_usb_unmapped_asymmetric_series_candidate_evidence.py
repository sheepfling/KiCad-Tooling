"""Source projection and report candidate for unmapped USB line asymmetry."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .usb_peer_reference_types import UsbPeerDataLink, UsbPeerReferencePathCoverage

USB_UNMAPPED_ASYMMETRIC_SERIES_RULE_ID: DesignLintRuleId = "bus.usb_unmapped_asymmetric_series"


@dataclass(frozen=True, slots=True)
class UsbUnmappedAsymmetricSeriesFindingEvidence:
    """Observed endpoint path and the exact authored map used for coverage."""

    path: UsbPeerReferencePathCoverage
    data_path: UsbDataPathCandidateInputs


def _line_evidence(
    link: UsbPeerDataLink,
    *,
    positive: bool,
) -> tuple[str, ...]:
    resistor = link.positive_series_resistor if positive else link.negative_series_resistor
    connector_pin = link.connector_positive_pin if positive else link.connector_negative_pin
    connector_net = link.connector_positive_net if positive else link.connector_negative_net
    phy_pin = link.phy_positive_pin if positive else link.phy_negative_pin
    phy_net = link.phy_positive_net if positive else link.phy_negative_net
    if resistor is None:
        return (f"direct: {connector_pin} on {connector_net} -> {phy_pin} on {phy_net}",)
    description = (
        f"{resistor.reference} {resistor.value} {resistor.symbol} {resistor.footprint}: "
        f"{resistor.connector_pin} on {resistor.connector_net} -> "
        f"{resistor.phy_pin} on {resistor.phy_net}"
    )
    return (description,)


def project_usb_unmapped_asymmetric_series_evidence(
    source: UsbUnmappedAsymmetricSeriesFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the typed topology and authored-map scope into stable fields."""
    path = source.path
    link = path.data_link
    series_line = "D+" if link.positive_series_resistor is not None else "D-"
    direct_line = "D-" if series_line == "D+" else "D+"
    evidence = {
        "connector": (path.connector_reference,),
        "PHY": (path.phy_reference,),
        "USB_D+_path": _line_evidence(link, positive=True),
        "USB_D-_path": _line_evidence(link, positive=False),
        "USB_series_resistor_line": (series_line,),
        "USB_direct_line": (direct_line,),
        "USB_topology_kind": ("one_data_line_series_resistor_other_direct",),
        "USB_data_map_state": ("no current map matches this connector/PHY port group",),
    }
    if link.port_group is not None:
        evidence["USB_port_group"] = (link.port_group,)
    if source.data_path.map_sha256 is not None:
        evidence["USB_data_path_map_sha256"] = (source.data_path.map_sha256,)
    return CandidateEvidenceProjection(
        rule_id=USB_UNMAPPED_ASYMMETRIC_SERIES_RULE_ID,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class UsbUnmappedAsymmetricSeriesCandidate(Candidate):
    """Review prompt whose evidence is derived from one typed path observation."""

    source_evidence: UsbUnmappedAsymmetricSeriesFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UsbUnmappedAsymmetricSeriesFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> UsbUnmappedAsymmetricSeriesCandidate:
        projection = project_usb_unmapped_asymmetric_series_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_usb_unmapped_asymmetric_series_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError(
                "USB asymmetric series evidence must match its typed source projection"
            )
