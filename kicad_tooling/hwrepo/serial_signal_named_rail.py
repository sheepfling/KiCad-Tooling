"""Review UART/USART signal pins assigned directly to named rails."""

from __future__ import annotations

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .named_rail_pin_evidence import assigned_named_rail_ic_pins
from .serial_participants import serial_function_role_and_channel

RULE_ID: DesignLintRuleId = "bus.serial_signal_on_named_rail"


def serial_signal_on_named_rail_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review a fitted IC's explicit UART/USART TX or RX pin on a named rail.

    Pin functions and net labels are clues for review. The candidate does not
    establish a required serial endpoint or prove an electrical defect.
    """
    candidates: list[Candidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        pin_role = serial_function_role_and_channel(item.function)
        if pin_role is None:
            continue

        role, channel = pin_role
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The native serial pin function indicates {role.upper()} on channel "
                    f"{channel!r}, while its single assigned net label ({item.net_name!r}) is "
                    f"recognized as {item.rail_role}. Review whether this is an intentional rail "
                    "strap or a pin-assignment issue. The function and label are review clues, "
                    "not proof of electrical potential, required serial connectivity, or a "
                    "defect; this check does not assess PCB copper or physical continuity."
                ),
                evidence={
                    "pin": (item.pin,),
                    "pin_function": (item.function,),
                    "pin_role": (role,),
                    "serial_channel": (channel,),
                    "assigned_net": (item.net_name,),
                    "net_label_role_clue": (item.rail_role,),
                    "component_pin_inventory": item.inventory,
                },
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
