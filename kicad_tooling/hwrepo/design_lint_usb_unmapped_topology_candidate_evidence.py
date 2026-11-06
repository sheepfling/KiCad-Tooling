"""Typed source and report projection for unmapped USB topology prompts."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .usb_peer_reference_types import UsbPeerUnsupportedMultiPinPath

USB_UNMAPPED_TOPOLOGY_RULE_ID: DesignLintRuleId = "bus.usb_unmapped_multi_pin_topology"


@dataclass(frozen=True, slots=True)
class UsbUnmappedMultiPinTopologyFindingEvidence:
    """One observed unsupported topology and the exact authored-map input."""

    path: UsbPeerUnsupportedMultiPinPath
    data_path: UsbDataPathCandidateInputs


def _pin_members(values: tuple[str, ...]) -> str:
    return ", ".join(sorted(values, key=lambda value: (value.casefold(), value)))


def project_usb_unmapped_multi_pin_topology_evidence(
    source: UsbUnmappedMultiPinTopologyFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the typed observation and map state into stable report fields."""
    path = source.path
    evidence = {
        "connector": (path.connector_reference,),
        "PHY": (path.phy_reference,),
        "multi_pin_component": (
            (
                f"{path.component_reference}: {path.component_symbol}; "
                f"{path.component_footprint}; {path.component_pin_count} native pins"
            ),
        ),
        "USB_data_map_state": ("no map matches this connector/PHY port group",),
    }
    if path.topology == "shared_data_net_attachment":
        evidence["USB_D+_shared_net"] = (
            (
                f"{path.positive_connector_net}: "
                f"{_pin_members(path.positive_connector_component_pins)}"
            ),
        )
        evidence["USB_D-_shared_net"] = (
            (
                f"{path.negative_connector_net}: "
                f"{_pin_members(path.negative_connector_component_pins)}"
            ),
        )
    else:
        evidence["USB_D+_connector_side"] = (
            (
                f"{path.positive_connector_net}: "
                f"{_pin_members(path.positive_connector_component_pins)}"
            ),
        )
        evidence["USB_D+_PHY_side"] = (
            f"{path.positive_phy_net}: {_pin_members(path.positive_phy_component_pins)}",
        )
        evidence["USB_D-_connector_side"] = (
            (
                f"{path.negative_connector_net}: "
                f"{_pin_members(path.negative_connector_component_pins)}"
            ),
        )
        evidence["USB_D-_PHY_side"] = (
            f"{path.negative_phy_net}: {_pin_members(path.negative_phy_component_pins)}",
        )
    evidence["USB_topology_kind"] = (path.topology,)
    if path.port_group is not None:
        evidence["USB_port_group"] = (path.port_group,)
    if source.data_path.map_sha256 is not None:
        evidence["USB_data_map_sha256"] = (source.data_path.map_sha256,)
    return CandidateEvidenceProjection(
        rule_id=USB_UNMAPPED_TOPOLOGY_RULE_ID,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class UsbUnmappedMultiPinTopologyCandidate(Candidate):
    """Coverage prompt retaining its exact unsupported topology and map input."""

    source_evidence: UsbUnmappedMultiPinTopologyFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UsbUnmappedMultiPinTopologyFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> UsbUnmappedMultiPinTopologyCandidate:
        projection = project_usb_unmapped_multi_pin_topology_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_usb_unmapped_multi_pin_topology_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("USB topology fields must match their typed source projection")
