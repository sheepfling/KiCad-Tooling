"""Build source-mapped USB data-path review candidates."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract, UsbDataPathMap
from .usb_data_paths import usb_data_path_mismatches


def usb_data_path_candidates(
    observed: NetlistContract,
    usb_data_path_map: UsbDataPathMap | None,
    usb_data_map_sha256: str | None,
) -> tuple[Candidate, ...]:
    found: list[Candidate] = []
    if usb_data_path_map is not None:
        map_sha256 = usb_data_map_sha256 or ""
        for mismatch in usb_data_path_mismatches(usb_data_path_map, observed):
            found.append(
                Candidate(
                    rule_id="bus.usb_data_path_mismatch",
                    subject=f"{mismatch.interface_id}: USB {mismatch.line} path",
                    message=(
                        "The connector-to-PHY USB reference pins or exact mapped bond differ "
                        "from the project-authored reference policy. Review the pins, nets, and "
                        "bond component; the map records schematic intent but does not prove "
                        "component conduction or PCB continuity."
                        if mismatch.line == "reference"
                        else "The connector-to-PHY USB data path differs from the project-authored, "
                        "PHY-specific topology. Review the exact pin assignments, fitted series "
                        "component, and manufacturer basis. This check does not infer a universal "
                        "USB resistor requirement or establish PCB continuity."
                    ),
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
                        "phy": (
                            (
                                f"{mismatch.phy_reference}: "
                                f"{mismatch.phy_symbol}; {mismatch.phy_footprint}"
                            ),
                        ),
                        "phy_pin": (mismatch.phy_pin,),
                        "expected_phy_net": (mismatch.phy_net,),
                        "expected_topology": (mismatch.expected_topology,),
                        "reference_policy": (
                            "none"
                            if mismatch.reference_policy is None
                            else mismatch.reference_policy,
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
                            else (
                                f"{mismatch.series_resistor_symbol}; "
                                f"{mismatch.series_resistor_footprint}"
                            ),
                        ),
                        "series_resistance_range_ohms": (
                            "none"
                            if mismatch.series_resistance_range_ohms is None
                            else (
                                f"{mismatch.series_resistance_range_ohms[0]:g}–"
                                f"{mismatch.series_resistance_range_ohms[1]:g} Ω"
                            ),
                        ),
                        "map_sha256": (map_sha256,),
                        "issues": mismatch.issues,
                    },
                )
            )
    return tuple(found)
