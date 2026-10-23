"""Translate CAN termination and peer-assignment observations."""

from __future__ import annotations

from .can_line_polarity import can_line_polarity_label_candidates
from .can_peer_heuristics import can_peer_assignment_divergences
from .can_peer_reference_scan import (
    CanPeerReferenceScan,
    scan_can_peer_references,
)
from .can_termination_heuristics import can_buses_without_local_termination
from .design_lint_types import Candidate
from .models import NetlistContract


def can_candidates(
    observed: NetlistContract,
    peer_reference_scan: CanPeerReferenceScan | None = None,
    component_peer_findings: tuple[Candidate, ...] = (),
) -> tuple[Candidate, ...]:
    """Build CAN termination and peer-assignment review prompts."""
    found: list[Candidate] = []
    for bus in can_buses_without_local_termination(observed):
        found.append(
            Candidate(
                rule_id="bus.can_missing_termination",
                subject=f"CANH {bus.high_net} / CANL {bus.low_net}",
                message=(
                    "No visible 108 Ω–132 Ω resistor is connected directly across these named "
                    "CAN lines. Review external or split termination and the intended bus topology."
                ),
                evidence={
                    "CANH": (bus.high_net,),
                    "CANL": (bus.low_net,),
                    "pins": (*bus.high_pins, *bus.low_pins),
                    "termination": (),
                },
            )
        )
    found.extend(can_line_polarity_label_candidates(observed))
    for divergence in can_peer_assignment_divergences(observed):
        found.append(
            Candidate(
                rule_id="bus.can_peer_assignment_divergence",
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
                evidence={
                    "shared_role": (divergence.shared_role,),
                    "shared_net": (divergence.shared_net,),
                    "complementary_role": (divergence.complementary_role,),
                    "complementary_nets": divergence.complementary_nets,
                    "participants": divergence.participants,
                },
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
        line_assignments = tuple(
            f"{item.reference}: {item.canh_pin} on {item.canh_net}; "
            f"{item.canl_pin} on {item.canl_net}"
            for item in bus.endpoints
        )
        reference_assignments = tuple(
            f"{item.reference}: "
            + (
                f"{', '.join(pin.pin for pin in item.reference_pins)} on {item.reference_net}"
                if item.reference_net is not None
                else "reference assignment incomplete"
            )
            for item in bus.endpoints
        )
        evidence = {
            "CANH": (bus.canh_net,),
            "CANL": (bus.canl_net,),
            "participants": participants,
            "line_assignments": line_assignments,
            "reference_assignments": reference_assignments,
        }
        if bus.incomplete_references:
            evidence["incomplete_reference_evidence"] = bus.incomplete_references
        found.append(
            Candidate(
                rule_id="bus.can_peer_reference_review",
                subject=f"CANH {bus.canh_net} / CANL {bus.canl_net}: {', '.join(participants)}",
                message=(
                    "Fitted CAN peers share the same native CANH/CANL net pair, and at least "
                    "two peers have explicit reference pins on separate nets. Review the "
                    "approved common, bonded, or isolated reference policy; this heuristic "
                    "does not require a common return or prove physical continuity."
                ),
                evidence=evidence,
            )
        )
    return tuple(found)
