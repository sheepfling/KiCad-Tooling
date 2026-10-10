"""Candidate translation for serial, USB, SPI, and digital-peer reviews."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from .design_lint_types import Candidate
from .digital_peer_voltage_scan import format_nominal_voltage, scan_digital_peer_voltage_reviews
from .digital_peer_voltage_types import DigitalPeerVoltageScan
from .models import DigitalPeerVoltageAnalysis, NetlistContract, UsbDataPathMap
from .serial_participants import SerialPeerRosterContext, unmapped_serial_peers
from .serial_peer_reference_scan import scan_serial_peer_reference_reviews
from .serial_peer_reference_types import SerialPeerReferenceScan
from .spi_participants import SpiRosterContext, unmapped_spi_participants
from .usb_c_ports import UsbCPortRosterContext, unmapped_usb_c_ports
from .usb_peer_reference_scan import scan_usb_peer_reference_reviews
from .usb_peer_reference_types import UsbPeerReferenceScan


@dataclass(frozen=True)
class DigitalPeerVoltageLintContext:
    """Project contract state and provenance for covered SPI and UART prompts."""

    state: Literal["not_configured", "pending", "not_applicable", "required"]
    analysis: DigitalPeerVoltageAnalysis | None = None
    source_path: str | None = None
    source_sha256: str | None = None


def usb_data_path_map_sha256(usb_data_path_map: UsbDataPathMap | None) -> str | None:
    """Return the stable evidence fingerprint used by USB review candidates."""
    if usb_data_path_map is None:
        return None
    return hashlib.sha256(usb_data_path_map.model_dump_json().encode("utf-8")).hexdigest()


def peer_candidates(
    observed: NetlistContract,
    *,
    digital_peer_voltage_context: DigitalPeerVoltageLintContext | None = None,
    digital_peer_voltage_scan: DigitalPeerVoltageScan | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
    serial_peer_reference_scan: SerialPeerReferenceScan | None = None,
    serial_peer_roster: SerialPeerRosterContext | None = None,
    spi_roster: SpiRosterContext | None = None,
    usb_c_port_roster: UsbCPortRosterContext | None = None,
    usb_data_path_map: UsbDataPathMap | None = None,
    usb_data_map_sha256: str | None = None,
    usb_peer_reference_scan: UsbPeerReferenceScan | None = None,
) -> tuple[Candidate, ...]:
    """Translate mapped peer and interface coverage into review candidates."""
    found: list[Candidate] = []
    serial_scope = serial_peer_roster or SerialPeerRosterContext(state="not_configured")
    serial_analysis = serial_scope.analysis
    for peer in unmapped_serial_peers(observed, serial_scope):
        if serial_scope.state == "required":
            scope_text = "is not listed in the project serial-peer map"
        elif serial_scope.state == "pending":
            scope_text = "is a candidate while the project serial-peer review remains pending"
        elif serial_scope.state == "not_applicable":
            scope_text = (
                "is a candidate despite the project serial-peer review being marked not applicable"
            )
        else:
            scope_text = "has no configured project serial-peer map"
        evidence = {
            "interface_channel": (peer.channel,),
            "TX_pins": peer.tx_pins,
            "RX_pins": peer.rx_pins,
            "assigned_signal_pins": peer.signal_assignments,
            "discovery_basis": (peer.discovery_basis,),
            "serial_peer_map_state": (serial_scope.state,),
        }
        if serial_scope.source_path is not None:
            evidence["electrical_contract_path"] = (serial_scope.source_path,)
        if serial_scope.source_sha256 is not None:
            evidence["electrical_contract_sha256"] = (serial_scope.source_sha256,)
        found.append(
            Candidate(
                rule_id="bus.serial_unmapped_peer",
                subject=(f"{peer.reference}: serial-peer map coverage ({peer.channel})"),
                message=(
                    f"{peer.reference} has "
                    + (
                        "assigned TX/RX-like pin functions"
                        if peer.discovery_basis == "pin_function"
                        else "assigned pins on explicitly UART/USART-labeled TX/RX nets"
                    )
                    + f" and {scope_text}. Review whether it is a missing logic-level UART "
                    "endpoint, an unused alternate function, or another interface. Net labels "
                    "are discovery clues only; this prompt does not assert that a peer or "
                    "connection is required."
                ),
                evidence=evidence,
            )
        )

    serial_reference_scan = serial_peer_reference_scan or scan_serial_peer_reference_reviews(
        observed, serial_analysis, reviewed_connector_references
    )
    for peer in serial_reference_scan.reviews:
        shared_links = tuple(
            f"{link.net}: {link.output_pin} ({link.output_function}, {link.output_type}) -> "
            f"{link.input_pin} ({link.input_function}, {link.input_type})"
            for link in peer.links
        )
        evidence = {
            "first_component": (peer.first_reference,),
            "second_component": (peer.second_reference,),
            "first_reference_net": (peer.first_reference_domain.net,),
            "first_reference_pin_assignments": tuple(
                f"{item.pin} ({item.function}, {item.electrical_type})={item.net}"
                for item in peer.first_reference_domain.pins
            ),
            "second_reference_net": (peer.second_reference_domain.net,),
            "second_reference_pin_assignments": tuple(
                f"{item.pin} ({item.function}, {item.electrical_type})={item.net}"
                for item in peer.second_reference_domain.pins
            ),
            "serial_peer_map_state": (serial_scope.state,),
        }
        if peer.links:
            evidence["shared_serial_pin_assignments"] = shared_links
        if peer.label_links:
            evidence["serial_label_link_assignments"] = tuple(
                f"{link.channel}: TX {link.tx_net} ({link.first_tx_pin}, {link.second_tx_pin}); "
                f"RX {link.rx_net} ({link.first_rx_pin}, {link.second_rx_pin})"
                for link in peer.label_links
            )
            evidence["discovery_basis"] = (
                ("native_pin_function", "net_label") if peer.links else ("net_label",)
            )
        if serial_scope.source_path is not None:
            evidence["electrical_contract_path"] = (serial_scope.source_path,)
        if serial_scope.source_sha256 is not None:
            evidence["electrical_contract_sha256"] = (serial_scope.source_sha256,)
        message = (
            "Source-bound UART TX and RX pins share a native signal net while their "
            "explicitly named reference pins use separate schematic nets. Review the "
            "approved interface requirement for a common reference, an explicit bond, "
            "or intentional isolation. This prompt does not establish board copper or "
            "off-board reference continuity."
        )
        if peer.label_links and not peer.links:
            message = (
                "Exact UART/USART TX and RX channel labels connect the same two fitted ICs, "
                "while their explicitly named reference pins use separate schematic nets. "
                "Review whether this is a direct peer or one segment of a translated path, "
                "and whether its references should be common, bonded, or intentionally "
                "separate. This prompt does not trace other components or establish board "
                "copper or off-board reference continuity."
            )
        found.append(
            Candidate(
                rule_id="bus.serial_peer_reference_review",
                subject=(
                    f"{peer.first_reference} / {peer.second_reference}: serial reference-domain review"
                ),
                message=message,
                evidence=evidence,
            )
        )

    usb_scan = usb_peer_reference_scan or scan_usb_peer_reference_reviews(
        observed, usb_data_path_map, reviewed_connector_references
    )
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

    spi_scope = spi_roster or SpiRosterContext(state="not_configured")
    for participant in unmapped_spi_participants(observed, spi_scope):
        if spi_scope.state == "required":
            scope_text = "is not listed in the project SPI device map"
        elif spi_scope.state == "pending":
            scope_text = "is a candidate while the project SPI review remains pending"
        elif spi_scope.state == "not_applicable":
            scope_text = "is a candidate despite the project SPI review being marked not applicable"
        else:
            scope_text = "has no configured project SPI device map"
        evidence = {
            "SCK_pins": participant.clock_pins,
            "input_data_pins": participant.input_data_pins,
            "output_data_pins": participant.output_data_pins,
            "chip_select_pins": participant.chip_select_pins,
            "assigned_signal_pins": participant.signal_assignments,
            "SPI_roster_state": (spi_scope.state,),
        }
        if spi_scope.source_path is not None:
            evidence["electrical_contract_path"] = (spi_scope.source_path,)
        if spi_scope.source_sha256 is not None:
            evidence["electrical_contract_sha256"] = (spi_scope.source_sha256,)
        found.append(
            Candidate(
                rule_id="bus.spi_unmapped_participant",
                subject=f"{participant.reference}: SPI roster coverage",
                message=(
                    f"{participant.reference} has assigned SPI-like clock/data pin functions and "
                    f"a named chip-select function, and {scope_text}. Review whether it is an "
                    "omitted device, an SPI controller, or a pin-function match for another "
                    "interface. This is a coverage prompt, not a finding that the design must "
                    "connect or include the device."
                ),
                evidence=evidence,
            )
        )

    peer_voltage_scope = digital_peer_voltage_context or DigitalPeerVoltageLintContext(
        state="not_configured"
    )
    peer_voltage_scan = digital_peer_voltage_scan or scan_digital_peer_voltage_reviews(
        observed, peer_voltage_scope.analysis
    )
    for peer in (item for item in peer_voltage_scan.reviews if item.interface == "SPI"):
        shared_links = tuple(
            f"{link.net}: {link.output_pin} ({link.output_function}, {link.output_type}) -> "
            f"{link.input_pin} ({link.input_function}, {link.input_type})"
            for link in peer.links
        )
        evidence = {
            "output_component": (peer.output_reference,),
            "input_component": (peer.input_reference,),
            "output_supply_net": (peer.output_rail.net,),
            "output_supply_label_value": (format_nominal_voltage(peer.output_rail.voltage_v),),
            "input_supply_net": (peer.input_rail.net,),
            "input_supply_label_value": (format_nominal_voltage(peer.input_rail.voltage_v),),
            "shared_SPI_pin_assignments": shared_links,
            "authored_voltage_map_state": (peer_voltage_scope.state,),
        }
        if peer_voltage_scope.source_path is not None:
            evidence["electrical_contract_path"] = (peer_voltage_scope.source_path,)
        if peer_voltage_scope.source_sha256 is not None:
            evidence["electrical_contract_sha256"] = (peer_voltage_scope.source_sha256,)
        found.append(
            Candidate(
                rule_id="bus.spi_peer_voltage_review",
                subject=(
                    f"{peer.output_reference} -> {peer.input_reference}: SPI voltage-domain review"
                ),
                message=(
                    "Source-bound native pins show an SPI output-capable endpoint and input-capable "
                    "peer on one net, while their uniquely identified power-input nets contain "
                    "different voltage-explicit labels. Treat those parsed label values as review "
                    "clues only. Confirm sourced supply, output, and receiver limits; this prompt "
                    "does not establish incompatibility or recommend level translation. A complete "
                    "exact digital-peer voltage map is checked separately."
                ),
                evidence=evidence,
            )
        )

    for peer in (item for item in peer_voltage_scan.reviews if item.interface == "serial"):
        shared_links = tuple(
            f"{link.net}: {link.output_pin} ({link.output_function}, {link.output_type}) -> "
            f"{link.input_pin} ({link.input_function}, {link.input_type})"
            for link in peer.links
        )
        evidence = {
            "output_component": (peer.output_reference,),
            "input_component": (peer.input_reference,),
            "output_supply_net": (peer.output_rail.net,),
            "output_supply_label_value": (format_nominal_voltage(peer.output_rail.voltage_v),),
            "input_supply_net": (peer.input_rail.net,),
            "input_supply_label_value": (format_nominal_voltage(peer.input_rail.voltage_v),),
            "shared_serial_pin_assignments": shared_links,
            "authored_voltage_map_state": (peer_voltage_scope.state,),
        }
        if peer_voltage_scope.source_path is not None:
            evidence["electrical_contract_path"] = (peer_voltage_scope.source_path,)
        if peer_voltage_scope.source_sha256 is not None:
            evidence["electrical_contract_sha256"] = (peer_voltage_scope.source_sha256,)
        found.append(
            Candidate(
                rule_id="bus.serial_peer_voltage_review",
                subject=(
                    f"{peer.output_reference} -> {peer.input_reference}: serial voltage-domain review"
                ),
                message=(
                    "Source-bound native pins show a UART-like TX output-capable endpoint and "
                    "RX input-capable peer on one net, while their uniquely identified power-input "
                    "nets contain different voltage-explicit labels. Treat those parsed label values "
                    "as review clues only. Confirm sourced supply, output, and receiver limits; this "
                    "prompt does not establish incompatibility or recommend level translation. A "
                    "complete exact digital-peer voltage map is checked separately."
                ),
                evidence=evidence,
            )
        )

    usb_c_scope = usb_c_port_roster or UsbCPortRosterContext(state="not_configured")
    if usb_c_scope.state == "required":
        usb_c_scope_text = "is not listed in the project USB-C port role map"
    elif usb_c_scope.state == "pending":
        usb_c_scope_text = "is a candidate while the project USB-C port review remains pending"
    elif usb_c_scope.state == "not_applicable":
        usb_c_scope_text = (
            "is a candidate despite the project USB-C review being marked not applicable"
        )
    else:
        usb_c_scope_text = "has no configured project USB-C port role map"
    for port in unmapped_usb_c_ports(observed, usb_c_scope, reviewed_connector_references):
        evidence = {
            "CC1_pins": port.cc1_pins,
            "CC2_pins": port.cc2_pins,
            "CC_assignments": port.signal_assignments,
            "USB_C_roster_state": (usb_c_scope.state,),
        }
        if usb_c_scope.source_path is not None:
            evidence["electrical_contract_path"] = (usb_c_scope.source_path,)
        if usb_c_scope.source_sha256 is not None:
            evidence["electrical_contract_sha256"] = (usb_c_scope.source_sha256,)
        found.append(
            Candidate(
                rule_id="bus.usb_c_unreviewed_port",
                subject=f"{port.reference}: USB-C role-map coverage",
                message=(
                    f"{port.reference} exports connector pin functions CC1 and CC2 and "
                    f"{usb_c_scope_text}. Review whether this is a USB-C port and, if so, "
                    "record its approved source, sink, or dual-role requirements. The pin names "
                    "do not establish port role, Rp/Rd, controller behavior, VBUS path, or "
                    "protection requirements."
                ),
                evidence=evidence,
            )
        )

    return tuple(found)
