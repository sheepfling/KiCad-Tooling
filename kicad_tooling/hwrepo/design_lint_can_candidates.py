"""Translate CAN termination and peer-assignment observations."""

from __future__ import annotations

from .can_line_named_rail import can_line_on_named_rail_candidates
from .can_line_polarity import can_line_polarity_label_candidates
from .can_peer_heuristics import can_peer_assignment_divergences
from .can_peer_reference_scan import (
    CanPeerReferenceScan,
    scan_can_peer_references,
)
from .can_signal_named_rail import can_signal_on_named_rail_candidates
from .can_termination_heuristics import (
    can_buses_with_excessive_local_termination,
    can_buses_without_local_termination,
)
from .can_tx_output_sharing import can_tx_output_sharing_candidates
from .can_tx_rx_label_mismatch import can_tx_rx_label_mismatch_candidates
from .can_tx_rx_same_net import can_tx_rx_same_net_candidates
from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_can_generic_connector_candidates import (
    generic_can_connector_pair_review_candidates,
)
from .design_lint_can_peer_candidate_evidence import CanPeerCandidate
from .design_lint_can_peer_reference_candidate_evidence import (
    CanPeerReferenceCandidate,
    CanPeerReferenceFindingEvidence,
)
from .design_lint_can_termination_candidate_evidence import CanTerminationCandidate
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract


def can_candidates(
    observed: NetlistContract,
    peer_reference_scan: CanPeerReferenceScan | None = None,
    component_peer_findings: tuple[Candidate, ...] = (),
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Build CAN termination and peer-assignment review prompts."""
    found: list[Candidate] = []
    for bus in can_buses_without_local_termination(observed):
        found.append(
            CanTerminationCandidate.from_source_evidence(
                source_evidence=bus,
                subject=f"CANH {bus.high_net} / CANL {bus.low_net}",
                message=(
                    "No visible 108 Ω–132 Ω resistor is connected directly across these named "
                    "CAN lines. Review external or split termination and the intended bus topology."
                ),
            )
        )
    for bus in can_buses_with_excessive_local_termination(observed):
        found.append(
            CanTerminationCandidate.from_source_evidence(
                source_evidence=bus,
                subject=f"CANH {bus.high_net} / CANL {bus.low_net}",
                message=(
                    f"{len(bus.terminations)} fitted direct 108 Ω–132 Ω resistors span this "
                    "recognized CANH/CANL pair. Review the intended bus endpoints and any "
                    "switchable, split, or external termination; the schematic does not show "
                    "which nodes are physical bus ends."
                ),
            )
        )
    found.extend(can_line_polarity_label_candidates(observed))
    found.extend(can_line_on_named_rail_candidates(observed))
    found.extend(can_signal_on_named_rail_candidates(observed))
    found.extend(can_tx_rx_same_net_candidates(observed))
    found.extend(can_tx_rx_label_mismatch_candidates(observed))
    found.extend(can_tx_output_sharing_candidates(observed))
    found.extend(
        generic_can_connector_pair_review_candidates(
            observed,
            reviewed_connector_references,
            connector_coverage,
        )
    )
    for divergence in can_peer_assignment_divergences(observed):
        found.append(
            CanPeerCandidate.from_source_evidence(
                source_evidence=divergence,
                subject=(
                    f"{divergence.shared_role} {divergence.shared_net}: "
                    "peer pair assignments diverge"
                ),
                message=(
                    f"Complete CAN pin pairs share {divergence.shared_role} net "
                    f"{divergence.shared_net}, but their {divergence.complementary_role} "
                    f"pins use multiple nets ({', '.join(divergence.complementary_nets)}). "
                    "Review whether the separate pair assignments are intentional; pin names "
                    "do not establish common-bus intent or physical connectivity."
                ),
            )
        )
    found.extend(
        can_peer_reference_candidates(
            observed,
            peer_reference_scan,
            component_peer_findings,
        )
    )
    return tuple(found)


def can_peer_reference_candidates(
    observed: NetlistContract,
    scan: CanPeerReferenceScan | None = None,
    component_peer_findings: tuple[Candidate, ...] = (),
) -> tuple[Candidate, ...]:
    """Build split-reference prompts not already covered by component-peer review."""
    reference_scan = scan or scan_can_peer_references(observed)
    component_reference_assignments = {
        (pin.casefold(), nets[0].casefold())
        for finding in component_peer_findings
        if (
            finding.rule_id == "component.peer_power_pin_assignment_divergence"
            and finding.evidence.get("peer_role") == ("ground/return",)
        )
        for pin, nets in finding.evidence.items()
        if "." in pin and len(nets) == 1
    }

    found: list[Candidate] = []
    for bus in reference_scan.reviews:
        expected_assignments = {
            (pin.pin.casefold(), pin.net.casefold())
            for endpoint in bus.endpoints
            for pin in endpoint.reference_pins
        }
        if (
            bus.disposition == "SPLIT_REFERENCE_REVIEW"
            and expected_assignments
            and expected_assignments <= component_reference_assignments
            and len({net for _, net in expected_assignments}) > 1
        ):
            continue
        participants = tuple(item.reference for item in bus.endpoints)
        found.append(
            CanPeerReferenceCandidate.from_source_evidence(
                CanPeerReferenceFindingEvidence(reference_scan, bus),
                subject=f"CANH {bus.canh_net} / CANL {bus.canl_net}: {', '.join(participants)}",
                message=(
                    "Fitted CAN peers share the same native CANH/CANL net pair, and at least "
                    "two peers have explicit reference pins on separate nets. Review the "
                    "approved common, bonded, or isolated reference policy; this heuristic "
                    "does not require a common return or prove physical continuity."
                ),
            )
        )
    return tuple(found)
