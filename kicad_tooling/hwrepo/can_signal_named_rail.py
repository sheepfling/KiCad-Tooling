"""Review CAN controller pins assigned directly to named rails."""

from __future__ import annotations

from .can_signal_functions import can_signal_role_and_channel
from .design_lint_named_rail_candidate_evidence import (
    CanSignalNamedRailEvidence,
    NamedRailSignalCandidate,
)
from .design_lint_rule_types import DesignLintRuleId
from .named_rail_pin_evidence import NamedRailPinSource, assigned_named_rail_ic_pins
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "bus.can_signal_on_named_rail"


def can_signal_on_named_rail_candidates(
    observed: NetlistContract,
) -> tuple[NamedRailSignalCandidate, ...]:
    """Review fitted CAN/FDCAN TX/RX IC pins assigned to a rail-like net label.

    Native pin-function names and rail-like net labels are clues only. A direct
    strap may be intentional for a particular transceiver or operating mode.
    """
    candidates: list[NamedRailSignalCandidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        role_channel = can_signal_role_and_channel(item.function)
        if role_channel is None:
            continue
        role, channel = role_channel
        candidates.append(
            NamedRailSignalCandidate.from_source_evidence(
                CanSignalNamedRailEvidence(
                    pin=NamedRailPinSource(observed=observed, evidence=item),
                    role=role,
                    channel=channel,
                ),
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The native CAN/FDCAN pin function indicates {role.upper()} on channel "
                    f"{channel!r}, while its single assigned net label ({item.net_name!r}) is "
                    f"recognized as {item.rail_role}. Review whether this is an intentional "
                    "rail strap or a pin-assignment issue. The function and label are review "
                    "clues, not proof of electrical potential, required CAN connectivity, or "
                    "a defect; this check does not assess PCB copper or physical continuity."
                ),
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
