"""Translate RS-485 data-role and mapped peer-reference review evidence."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .rs485_data_label_mismatch import rs485_data_direction_label_candidates
from .rs485_peer_reference_types import Rs485PeerReferenceScan
from .rs485_same_net import rs485_data_input_output_same_net_candidates
from .rs485_unconnected_data_pins import rs485_unconnected_data_pin_candidates


def rs485_candidates(
    observed: NetlistContract,
    scan: Rs485PeerReferenceScan | None = None,
    component_peer_findings: tuple[Candidate, ...] = (),
) -> tuple[Candidate, ...]:
    """Combine RS-485 data-role and mapped reference-review candidates."""
    reference_candidates = (
        rs485_peer_reference_candidates(scan, component_peer_findings) if scan is not None else ()
    )
    return (
        *reference_candidates,
        *rs485_data_direction_label_candidates(observed),
        *rs485_data_input_output_same_net_candidates(observed),
        *rs485_unconnected_data_pin_candidates(observed),
    )


def rs485_peer_reference_candidates(
    scan: Rs485PeerReferenceScan,
    component_peer_findings: tuple[Candidate, ...] = (),
) -> tuple[Candidate, ...]:
    """Prompt on explicit reference-net splits among mapped fitted RS-485 peers."""
    component_assignments = {
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
    for pair in scan.reviews:
        expected_assignments = {
            (pin.pin.casefold(), pin.net.casefold())
            for endpoint in pair.endpoints
            for pin in endpoint.reference_pins
            if pin.net is not None
        }
        if (
            pair.disposition == "SPLIT_REFERENCE_REVIEW"
            and expected_assignments
            and expected_assignments <= component_assignments
        ):
            continue
        participants = tuple(item.reference for item in pair.endpoints)
        reference_assignments = tuple(
            f"{item.reference}: "
            + (
                ", ".join(f"{pin.pin} on {pin.net or 'unassigned'}" for pin in item.reference_pins)
                if item.reference_pins
                else "no mapped reference pin"
            )
            for item in pair.endpoints
        )
        evidence = {
            "bus": (pair.bus_id,),
            "pair": (pair.pair_id,),
            "line_1": (pair.line_1_net,),
            "line_2": (pair.line_2_net,),
            "participants": participants,
            "reference_assignments": reference_assignments,
            "reference_nets": tuple(
                sorted(
                    {item.reference_net for item in pair.endpoints if item.reference_net},
                    key=lambda item: (item.casefold(), item),
                )
            ),
        }
        if pair.incomplete_references:
            evidence["incomplete_reference_evidence"] = pair.incomplete_references
        found.append(
            Candidate(
                rule_id="bus.rs485_peer_reference_review",
                subject=(
                    f"RS-485 bus {pair.bus_id} pair {pair.pair_id}: {', '.join(participants)}"
                ),
                message=(
                    "Mapped fitted RS-485 endpoints share the exact native line pair, and at "
                    "least two have explicit reference pins on separate nets. Review the "
                    "approved common, bonded, or isolated reference policy; this heuristic "
                    "does not require a common return or prove physical continuity."
                ),
                evidence=evidence,
            )
        )
    return tuple(found)
