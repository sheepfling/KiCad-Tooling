"""Review Ethernet data pins assigned directly to named rails."""

from __future__ import annotations

from .bus_signal_pairs import ethernet_data_pair_function_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .named_rail_pin_evidence import assigned_named_rail_ic_pins

RULE_ID: DesignLintRuleId = "bus.ethernet_signal_on_named_rail"


def ethernet_signal_on_named_rail_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review fitted Ethernet PHY TX/RX pins assigned to rail-like net labels.

    The bounded native function and net-name clues do not establish whether a
    direct rail connection is wrong. PHY strap modes and unused pins remain
    project-specific decisions.
    """
    candidates: list[Candidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        direction_side = ethernet_data_pair_function_role(item.function)
        if direction_side is None:
            continue
        direction, side = direction_side
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The native Ethernet data-pair function identifies {direction} "
                    f"{side} on this fitted IC pin, while its single assigned net label "
                    f"({item.net_name!r}) is recognized as {item.rail_role}. Review whether "
                    "this is an intentional PHY strap or a pin-assignment issue. Function "
                    "and label clues do not establish electrical potential, required "
                    "connectivity, routed copper, or physical continuity."
                ),
                evidence={
                    "pin": (item.pin,),
                    "pin_function": (item.function,),
                    "ethernet_direction": (direction,),
                    "ethernet_pair_side": (side,),
                    "assigned_net": (item.net_name,),
                    "net_label_role_clue": (item.rail_role,),
                    "component_pin_inventory": item.inventory,
                },
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
