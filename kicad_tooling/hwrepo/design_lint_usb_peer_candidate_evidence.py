"""Typed source projections for USB peer-reference candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .usb_data_path_models import UsbDataPathMap
from .usb_peer_reference_types import (
    UsbPeerReferenceComponentObservation,
    UsbPeerReferenceReview,
    UsbPeerReferenceScan,
)


@dataclass(frozen=True, slots=True)
class UsbPeerReferenceFindingEvidence:
    """One exact review, its parent scan, and the authored data-path input."""

    scan: UsbPeerReferenceScan
    review: UsbPeerReferenceReview
    data_path: UsbDataPathCandidateInputs

    def __post_init__(self) -> None:
        if not any(review is self.review for review in self.scan.reviews):
            raise ValueError("USB peer review must belong to its source scan")


_USB_PEER_REFERENCE_REVIEW: DesignLintRuleId = "bus.usb_peer_reference_review"


def _reference_component_observation(component: UsbPeerReferenceComponentObservation) -> str:
    symbol = component.symbol or "symbol metadata unavailable"
    value = component.value or "value metadata unavailable"
    footprint = component.footprint or "footprint metadata unavailable"
    dnp_state = "listed" if component.dnp_metadata_listed else "not listed"
    assignments = "; ".join(
        f"{pin.pin} (function={pin.function or 'unavailable'}, "
        f"type={pin.electrical_type or 'unavailable'})={pin.net}"
        for pin in component.pin_assignments
    )
    return (
        f"{component.reference}: {symbol}; value={value}; footprint={footprint}; "
        f"DNP metadata={dnp_state}; exact normalized schematic-netlist pin assignments: "
        f"{assignments}"
    )


def _reference_policy_state(
    review: UsbPeerReferenceReview,
    data_path: UsbDataPathCandidateInputs,
) -> str:
    usb_data_path_map: UsbDataPathMap | None = data_path.authored_map
    if usb_data_path_map is None:
        return "no_data_path_map"
    if review.data_link.connector_signal_family.startswith("USB SuperSpeed "):
        return "USB_2.0_map_not_applicable"
    matching_interfaces = tuple(
        interface
        for interface in usb_data_path_map.interfaces
        if interface.connector_reference.casefold() == review.connector_reference.casefold()
        and interface.phy_reference.casefold() == review.phy_reference.casefold()
    )
    if not matching_interfaces:
        return "no_matching_interface_map"
    if all(interface.reference_policy is None for interface in matching_interfaces):
        return "not_configured"
    return "configured_but_not_matching_observation"


def project_usb_peer_reference_evidence(
    source: UsbPeerReferenceFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project one source-bound USB peer review into stable finding fields."""
    peer = source.review
    usb_data_path_map: UsbDataPathMap | None = source.data_path.authored_map
    is_superspeed = peer.data_link.connector_signal_family.startswith("USB SuperSpeed ")
    positive_link_key = "USB_SuperSpeed_positive_link" if is_superspeed else "USB_D+_link"
    negative_link_key = "USB_SuperSpeed_negative_link" if is_superspeed else "USB_D-_link"

    positive_link = (
        f"{', '.join(peer.data_link.connector_positive_pins)} / "
        f"{', '.join(peer.data_link.phy_positive_pins)}"
    )
    negative_link = (
        f"{', '.join(peer.data_link.connector_negative_pins)} / "
        f"{', '.join(peer.data_link.phy_negative_pins)}"
    )
    if peer.data_link.positive_inline_component is not None:
        positive_link += (
            f"={peer.data_link.connector_positive_net} to "
            f"{peer.data_link.phy_positive_net} through mapped inline component "
            f"{peer.data_link.positive_inline_component.reference}"
        )
    elif peer.data_link.positive_series_resistor is None:
        positive_link += f"={peer.data_link.connector_positive_net}"
    else:
        positive_link += (
            f"={peer.data_link.connector_positive_net} to "
            f"{peer.data_link.phy_positive_net} through "
            f"{peer.data_link.positive_series_resistor.reference}"
        )
    if peer.data_link.negative_inline_component is not None:
        negative_link += (
            f"={peer.data_link.connector_negative_net} to "
            f"{peer.data_link.phy_negative_net} through mapped inline component "
            f"{peer.data_link.negative_inline_component.reference}"
        )
    elif peer.data_link.negative_series_resistor is None:
        negative_link += f"={peer.data_link.connector_negative_net}"
    else:
        negative_link += (
            f"={peer.data_link.connector_negative_net} to "
            f"{peer.data_link.phy_negative_net} through "
            f"{peer.data_link.negative_series_resistor.reference}"
        )

    evidence = {
        "connector": (
            f"{peer.connector_reference}: {peer.connector_symbol}; {peer.connector_footprint}",
        ),
        "phy": (f"{peer.phy_reference}: {peer.phy_symbol}; {peer.phy_footprint}",),
        "connector_reference_net": (peer.connector_reference_net,),
        "connector_reference_pin_assignments": tuple(
            f"{item.pin} ({item.function}, {item.electrical_type})={item.net}"
            for item in peer.connector_reference_pins
        ),
        "phy_reference_net": (peer.phy_reference_net,),
        "phy_reference_pin_assignments": tuple(
            f"{item.pin} ({item.function}, {item.electrical_type})={item.net}"
            for item in peer.phy_reference_pins
        ),
        positive_link_key: (positive_link,),
        negative_link_key: (negative_link,),
        "USB_data_map_state": (
            "configured" if usb_data_path_map is not None else "not_configured",
        ),
        "USB_reference_policy_state": (_reference_policy_state(peer, source.data_path),),
        "USB_components_with_pins_on_both_reference_nets": (
            tuple(
                _reference_component_observation(item)
                for item in peer.reference_component_observations
            )
            or (
                (
                    "No non-endpoint component has uniquely assigned pins on both endpoint "
                    "reference nets in the normalized schematic netlist."
                ),
            )
        ),
    }
    if is_superspeed:
        evidence["USB_connector_pair_family"] = (peer.data_link.connector_signal_family,)
        evidence["USB_PHY_pair_family"] = (peer.data_link.phy_signal_family,)
    if peer.data_link.port_group is not None:
        evidence["USB_port_group"] = (peer.data_link.port_group,)
    if peer.data_link.positive_shunt_branches:
        evidence["USB_D+_shunt_branches"] = tuple(
            f"{branch.data_pin} ({branch.symbol}) to {branch.reference_pin}={branch.reference_net}"
            for branch in peer.data_link.positive_shunt_branches
        )
    if peer.data_link.negative_shunt_branches:
        evidence["USB_D-_shunt_branches"] = tuple(
            f"{branch.data_pin} ({branch.symbol}) to {branch.reference_pin}={branch.reference_net}"
            for branch in peer.data_link.negative_shunt_branches
        )
    if peer.data_link.protection_shunts:
        evidence["USB_mapped_protection_shunts"] = tuple(
            f"{item.reference} ({item.symbol}; {item.footprint})"
            for item in peer.data_link.protection_shunts
        )
        evidence["USB_mapped_protection_shunt_pin_assignments"] = tuple(
            assignment
            for item in peer.data_link.protection_shunts
            for assignment in item.pin_assignments
        )
    if peer.data_link.positive_series_resistor is not None:
        resistor = peer.data_link.positive_series_resistor
        evidence["USB_D+_series_resistor"] = (
            (
                f"{resistor.reference} ({resistor.symbol}, {resistor.value or 'unspecified'}; "
                f"{resistor.connector_pin}={resistor.connector_net}, "
                f"{resistor.phy_pin}={resistor.phy_net})"
            ),
        )
    if peer.data_link.negative_series_resistor is not None:
        resistor = peer.data_link.negative_series_resistor
        evidence["USB_D-_series_resistor"] = (
            (
                f"{resistor.reference} ({resistor.symbol}, {resistor.value or 'unspecified'}; "
                f"{resistor.connector_pin}={resistor.connector_net}, "
                f"{resistor.phy_pin}={resistor.phy_net})"
            ),
        )
    if peer.data_link.positive_inline_component is not None:
        inline = peer.data_link.positive_inline_component
        evidence["USB_inline_component"] = (
            f"{inline.reference} ({inline.symbol}; {inline.footprint})",
        )
        evidence["USB_inline_component_pin_assignments"] = inline.pin_assignments
    if source.data_path.map_sha256 is not None:
        evidence["USB_data_map_sha256"] = (source.data_path.map_sha256,)
    return CandidateEvidenceProjection(rule_id=_USB_PEER_REFERENCE_REVIEW, evidence=evidence)


@dataclass(frozen=True, slots=True)
class UsbPeerReferenceCandidate(Candidate):
    """USB reference prompt retaining its exact scan, review, and map input."""

    source_evidence: UsbPeerReferenceFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UsbPeerReferenceFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> UsbPeerReferenceCandidate:
        projection = project_usb_peer_reference_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_usb_peer_reference_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("USB peer fields must match their typed source projection")
