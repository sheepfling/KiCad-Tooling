"""Typed USB data-path finding sources and their stable report projection."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_types import Candidate, CandidateEvidenceProjection
from .usb_data_path_types import UsbDataPathMismatch


@dataclass(frozen=True, slots=True)
class UsbDataPathFindingEvidence:
    """One compared USB path and the authored map identity behind it."""

    mismatch: UsbDataPathMismatch
    map_sha256: str


UsbDataPathEvidenceProjection = CandidateEvidenceProjection


def project_usb_data_path_evidence(
    source: UsbDataPathFindingEvidence,
) -> UsbDataPathEvidenceProjection:
    """Project typed comparison evidence to the established report fields."""
    mismatch = source.mismatch
    return UsbDataPathEvidenceProjection(
        rule_id="bus.usb_data_path_mismatch",
        evidence={
            "interface": (mismatch.interface_id,),
            "basis": (mismatch.basis,),
            "line": (mismatch.line,),
            "connector": (
                (
                    f"{mismatch.connector_reference}: "
                    f"{mismatch.connector_symbol}; {mismatch.connector_footprint}"
                ),
            ),
            "connector_pin": (mismatch.connector_pin,),
            "expected_connector_net": (mismatch.connector_net,),
            "phy": (f"{mismatch.phy_reference}: {mismatch.phy_symbol}; {mismatch.phy_footprint}",),
            "phy_pin": (mismatch.phy_pin,),
            "expected_phy_net": (mismatch.phy_net,),
            "expected_topology": (mismatch.expected_topology,),
            "reference_policy": (
                "none" if mismatch.reference_policy is None else mismatch.reference_policy,
            ),
            "reference_bond": (
                "none"
                if mismatch.reference_bond_reference is None
                else mismatch.reference_bond_reference,
            ),
            "reference_bond_identity": (
                "none"
                if mismatch.reference_bond_identity is None
                else mismatch.reference_bond_identity,
            ),
            "reference_bond_side_a": (
                "none"
                if mismatch.reference_bond_side_a is None
                else mismatch.reference_bond_side_a,
            ),
            "reference_bond_side_b": (
                "none"
                if mismatch.reference_bond_side_b is None
                else mismatch.reference_bond_side_b,
            ),
            "series_resistor": (
                "none"
                if mismatch.series_resistor_reference is None
                else mismatch.series_resistor_reference,
            ),
            "series_resistor_identity": (
                "none"
                if mismatch.series_resistor_reference is None
                else f"{mismatch.series_resistor_symbol}; {mismatch.series_resistor_footprint}",
            ),
            "series_resistance_range_ohms": (
                "none"
                if mismatch.series_resistance_range_ohms is None
                else (
                    f"{mismatch.series_resistance_range_ohms[0]:g}–"
                    f"{mismatch.series_resistance_range_ohms[1]:g} Ω"
                ),
            ),
            "inline_component": (mismatch.inline_component_reference or "none",),
            "inline_component_identity": (mismatch.inline_component_identity or "none",),
            "inline_component_pin_assignments": (
                mismatch.inline_component_pin_assignments or ("none",)
            ),
            "protection_shunt": (mismatch.protection_shunt_reference or "none",),
            "protection_shunt_identity": (mismatch.protection_shunt_identity or "none",),
            "protection_shunt_pin_assignments": (
                mismatch.protection_shunt_pin_assignments or ("none",)
            ),
            "map_sha256": (source.map_sha256,),
            "issues": mismatch.issues,
        },
    )


@dataclass(frozen=True, slots=True)
class UsbDataPathCandidate(Candidate):
    """Internal USB finding retaining its compared source record."""

    source_evidence: UsbDataPathFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UsbDataPathFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> UsbDataPathCandidate:
        projection = project_usb_data_path_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_usb_data_path_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("USB data-path evidence belongs to its mapped-path rule")
        if self.evidence != projection.evidence:
            raise ValueError("USB data-path evidence must match its typed source projection")
