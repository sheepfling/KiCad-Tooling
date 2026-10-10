"""Translate CAN termination and peer-assignment observations."""

from __future__ import annotations

from .can_peer_heuristics import can_peer_assignment_divergences
from .can_termination_heuristics import can_buses_without_local_termination
from .design_lint_types import Candidate
from .models import NetlistContract


def can_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
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
    return tuple(found)
