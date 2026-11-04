"""Translate digital-peer voltage-domain review observations."""

from __future__ import annotations

from .design_lint_digital_peer_voltage_candidate_evidence import (
    DigitalPeerVoltageCandidate,
    DigitalPeerVoltageFindingEvidence,
)
from .design_lint_types import Candidate
from .digital_peer_voltage_types import DigitalPeerVoltageLintContext, DigitalPeerVoltageScan


def digital_peer_voltage_candidates(
    peer_voltage_scope: DigitalPeerVoltageLintContext,
    peer_voltage_scan: DigitalPeerVoltageScan,
) -> tuple[Candidate, ...]:
    """Build mapped SPI and serial voltage-domain REVIEW prompts."""
    found: list[Candidate] = []
    for peer in (item for item in peer_voltage_scan.reviews if item.interface == "SPI"):
        found.append(
            DigitalPeerVoltageCandidate.from_source_evidence(
                DigitalPeerVoltageFindingEvidence(peer, peer_voltage_scope),
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
            )
        )

    for peer in (item for item in peer_voltage_scan.reviews if item.interface == "serial"):
        found.append(
            DigitalPeerVoltageCandidate.from_source_evidence(
                DigitalPeerVoltageFindingEvidence(peer, peer_voltage_scope),
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
            )
        )
    return tuple(found)
