"""Review fitted USB data pins assigned directly to named rails."""

from __future__ import annotations

from .bus_signal_pairs import usb_data_function_identity, usb_superspeed_function_identity
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .named_rail_pin_evidence import assigned_named_rail_ic_pins

RULE_ID: DesignLintRuleId = "bus.usb_signal_on_named_rail"


def _usb_signal_identity(function: str) -> tuple[str, str] | None:
    data_identity = usb_data_function_identity(function)
    if data_identity is not None:
        port, side = data_identity
        family = "USB 2.0 data" if port is None else f"USB 2.0 data port {port}"
        return family, side

    superspeed_identity = usb_superspeed_function_identity(function)
    if superspeed_identity is not None:
        family, side = superspeed_identity
        return family, side
    return None


def usb_signal_on_named_rail_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review fitted IC USB data pins assigned to one named supply or return rail.

    Pin-function and net-label vocabularies are bounded clues. A rail-looking
    assignment can also be an intentional strap, so this predicate requests
    review instead of asserting a required connection or electrical defect.
    """
    candidates: list[Candidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        identity = _usb_signal_identity(item.function)
        if identity is None:
            continue
        family, side = identity
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The native {family} pin function identifies the {side} side, while its "
                    f"single assigned net label ({item.net_name!r}) is recognized as "
                    f"{item.rail_role}. Review whether this direct assignment is intentional. "
                    "Function and label clues do not establish electrical potential, required "
                    "connectivity, routed copper, or physical continuity."
                ),
                evidence={
                    "pin": (item.pin,),
                    "pin_function": (item.function,),
                    "usb_signal_family": (family,),
                    "usb_pair_side": (side,),
                    "assigned_net": (item.net_name,),
                    "net_label_role_clue": (item.rail_role,),
                    "component_pin_inventory": item.inventory,
                },
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
