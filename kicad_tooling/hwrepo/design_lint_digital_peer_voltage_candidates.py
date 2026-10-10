"""Translate digital-peer voltage-domain review observations."""

from __future__ import annotations

from .design_lint_types import Candidate
from .digital_peer_voltage_scan import format_nominal_voltage
from .digital_peer_voltage_types import DigitalPeerVoltageLintContext, DigitalPeerVoltageScan


def digital_peer_voltage_candidates(
    peer_voltage_scope: DigitalPeerVoltageLintContext,
    peer_voltage_scan: DigitalPeerVoltageScan,
) -> tuple[Candidate, ...]:
    """Build mapped SPI and serial voltage-domain REVIEW prompts."""
    found: list[Candidate] = []
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
    return tuple(found)
