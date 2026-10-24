"""Review Ethernet management pins assigned directly to named rails."""

from __future__ import annotations

from .bus_signal_pairs import ethernet_management_function_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .named_rail_pin_evidence import assigned_named_rail_ic_pins

RULE_ID: DesignLintRuleId = "bus.ethernet_management_signal_on_named_rail"


def ethernet_management_signal_on_named_rail_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review fitted Ethernet MDC/MDIO pins directly assigned to named rails."""
    candidates: list[Candidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        role = ethernet_management_function_role(item.function)
        if role is None:
            continue
        role_name = "management clock" if role == "clock" else "management data"
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The native Ethernet {role_name} pin function is assigned to a net whose "
                    f"label ({item.net_name!r}) is recognized as {item.rail_role}. Review "
                    "whether this direct assignment is intentional. Function and label clues "
                    "do not establish electrical potential, required connectivity, routed "
                    "copper, or physical continuity."
                ),
                evidence={
                    "pin": (item.pin,),
                    "pin_function": (item.function,),
                    "ethernet_management_role": (role,),
                    "assigned_net": (item.net_name,),
                    "net_label_role_clue": (item.rail_role,),
                    "component_pin_inventory": item.inventory,
                },
            )
        )
    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
