"""Review I2C controller signal pins assigned directly to named rails."""

from __future__ import annotations

from .bus_signal_roles import i2c_signal_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .named_rail_pin_evidence import assigned_named_rail_ic_pins

RULE_ID: DesignLintRuleId = "bus.i2c_signal_on_named_rail"


def i2c_signal_on_named_rail_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review a fitted IC's explicit SDA/SCL pin when assigned directly to a named rail.

    The pin function and net label are review clues. This check does not infer
    that the rail connection is wrong or that the I2C endpoint is required.
    """
    candidates: list[Candidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        pin_role = i2c_signal_role(item.function)
        if pin_role is None:
            continue

        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The native I2C pin function is {pin_role}, while its single assigned "
                    f"net label ({item.net_name!r}) is recognized as {item.rail_role}. Review whether "
                    "this is an intentional rail strap or a pin-assignment issue. The function "
                    "and label are review clues, not proof of electrical potential, required "
                    "bus membership, or a defect; this check does not assess PCB copper or "
                    "physical continuity."
                ),
                evidence={
                    "pin": (item.pin,),
                    "pin_function": (item.function,),
                    "pin_role": (pin_role,),
                    "assigned_net": (item.net_name,),
                    "net_label_role_clue": (item.rail_role,),
                    "component_pin_inventory": item.inventory,
                },
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
