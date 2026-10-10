"""Translate serial-peer coverage, reference, and voltage reviews."""

from __future__ import annotations

from .design_lint_types import Candidate
from .digital_peer_voltage_scan import format_nominal_voltage
from .digital_peer_voltage_types import DigitalPeerVoltageLintContext, DigitalPeerVoltageScan
from .models import NetlistContract
from .serial_participants import SerialPeerRosterContext, unmapped_serial_peers
from .serial_peer_reference_types import SerialPeerReferenceScan


def serial_unmapped_peer_candidates(
    observed: NetlistContract,
    serial_scope: SerialPeerRosterContext,
) -> tuple[Candidate, ...]:
    """Build coverage prompts for likely serial peers missing from the roster."""
    found: list[Candidate] = []
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
    return tuple(found)


def serial_reference_candidates(
    serial_reference_scan: SerialPeerReferenceScan,
    serial_scope: SerialPeerRosterContext,
) -> tuple[Candidate, ...]:
    """Build source-bound serial reference-domain review prompts."""
    found: list[Candidate] = []
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
    return tuple(found)


def serial_voltage_candidates(
    peer_voltage_scope: DigitalPeerVoltageLintContext,
    peer_voltage_scan: DigitalPeerVoltageScan,
) -> tuple[Candidate, ...]:
    """Build REVIEW prompts for mapped serial peers across named voltage domains."""
    found: list[Candidate] = []
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
    return tuple(found)
