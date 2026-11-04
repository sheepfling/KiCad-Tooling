"""Translate serial-peer coverage, reference, and voltage reviews."""

from __future__ import annotations

from .design_lint_digital_peer_voltage_candidate_evidence import (
    DigitalPeerVoltageCandidate,
    DigitalPeerVoltageFindingEvidence,
)
from .design_lint_serial_peer_candidate_evidence import (
    SerialPeerCandidate,
    SerialPeerReferenceFindingEvidence,
    UnmappedSerialPeerFindingEvidence,
)
from .design_lint_types import Candidate
from .digital_peer_voltage_types import DigitalPeerVoltageLintContext, DigitalPeerVoltageScan
from .netlist_contract_models import NetlistContract
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
        found.append(
            SerialPeerCandidate.from_source_evidence(
                UnmappedSerialPeerFindingEvidence(peer, serial_scope),
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
            SerialPeerCandidate.from_source_evidence(
                SerialPeerReferenceFindingEvidence(serial_reference_scan, peer, serial_scope),
                subject=(
                    f"{peer.first_reference} / {peer.second_reference}: serial reference-domain review"
                ),
                message=message,
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
