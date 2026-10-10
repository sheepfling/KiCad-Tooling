"""Translate USB peer-reference observations and map evidence."""

from __future__ import annotations

import hashlib

from .design_lint_types import Candidate
from .models import UsbDataPathMap
from .usb_peer_reference_types import UsbPeerReferenceScan


def usb_data_path_map_sha256(usb_data_path_map: UsbDataPathMap | None) -> str | None:
    """Return the stable evidence fingerprint used by USB review candidates."""
    if usb_data_path_map is None:
        return None
    return hashlib.sha256(usb_data_path_map.model_dump_json().encode("utf-8")).hexdigest()


def usb_peer_reference_candidates(
    usb_scan: UsbPeerReferenceScan,
    usb_data_path_map: UsbDataPathMap | None,
    usb_data_map_sha256: str | None,
) -> tuple[Candidate, ...]:
    """Build bounded USB connector-to-PHY reference-domain review prompts."""
    found: list[Candidate] = []
    for peer in usb_scan.reviews:
        connector_identity = (
            f"{peer.connector_reference}: {peer.connector_symbol}; {peer.connector_footprint}"
        )
        positive_link = (
            f"{', '.join(peer.data_link.connector_positive_pins)} / "
            f"{', '.join(peer.data_link.phy_positive_pins)}"
        )
        negative_link = (
            f"{', '.join(peer.data_link.connector_negative_pins)} / "
            f"{', '.join(peer.data_link.phy_negative_pins)}"
        )
        if peer.data_link.positive_series_resistor is None:
            positive_link += f"={peer.data_link.connector_positive_net}"
        else:
            positive_link += (
                f"={peer.data_link.connector_positive_net} to "
                f"{peer.data_link.phy_positive_net} through "
                f"{peer.data_link.positive_series_resistor.reference}"
            )
        if peer.data_link.negative_series_resistor is None:
            negative_link += f"={peer.data_link.connector_negative_net}"
        else:
            negative_link += (
                f"={peer.data_link.connector_negative_net} to "
                f"{peer.data_link.phy_negative_net} through "
                f"{peer.data_link.negative_series_resistor.reference}"
            )
        evidence = {
            "connector": (connector_identity,),
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
            "USB_D+_link": (positive_link,),
            "USB_D-_link": (negative_link,),
            "USB_data_map_state": (
                "configured" if usb_data_path_map is not None else "not_configured",
            ),
        }
        if peer.data_link.port_group is not None:
            evidence["USB_port_group"] = (peer.data_link.port_group,)
        if peer.data_link.positive_shunt_branches:
            evidence["USB_D+_shunt_branches"] = tuple(
                f"{branch.data_pin} ({branch.symbol}) to "
                f"{branch.reference_pin}={branch.reference_net}"
                for branch in peer.data_link.positive_shunt_branches
            )
        if peer.data_link.negative_shunt_branches:
            evidence["USB_D-_shunt_branches"] = tuple(
                f"{branch.data_pin} ({branch.symbol}) to "
                f"{branch.reference_pin}={branch.reference_net}"
                for branch in peer.data_link.negative_shunt_branches
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
        if usb_data_map_sha256 is not None:
            evidence["USB_data_map_sha256"] = (usb_data_map_sha256,)
        found.append(
            Candidate(
                rule_id="bus.usb_peer_reference_review",
                subject=(
                    f"{peer.connector_reference} / {peer.phy_reference}: "
                    "USB reference-domain review"
                    + (
                        f" (port {peer.data_link.port_group})"
                        if peer.data_link.port_group is not None
                        else ""
                    )
                ),
                message=(
                    "Supported USB 2.0 D+ and D- connector-to-PHY paths (direct or through one "
                    "fitted two-pin series resistor per line) have separate explicit endpoint "
                    "reference nets. Review whether this interface needs a common reference, an "
                    "explicit bond, or intentional isolation. Pin functions and the bounded "
                    "topology only identify a candidate; this prompt does not prove the required "
                    "relationship, component behavior, PCB copper, or off-board continuity."
                ),
                evidence=evidence,
            )
        )
    return tuple(found)
