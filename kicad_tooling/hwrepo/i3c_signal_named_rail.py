"""Review I3C signal pins assigned directly to named rails."""

from __future__ import annotations

from .bus_signal_roles import i3c_signal_identity
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .named_rail_pin_evidence import assigned_named_rail_ic_pins

RULE_ID: DesignLintRuleId = "bus.i3c_signal_on_named_rail"


def i3c_signal_on_named_rail_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review fitted IC I3C pins assigned to a supply-like or return-like label.

    An exact SDA/SCL pair must share one optional channel index. The function
    and net label are review clues; they do not establish I3C use or a defect.
    """
    pins_by_reference: dict[str, dict[tuple[str | None, str], list[str]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        identity = i3c_signal_identity(function)
        if not separator or not number or identity is None:
            continue
        roles = pins_by_reference.setdefault(reference.casefold(), {})
        roles.setdefault((identity.channel, identity.role), []).append(pin)

    candidates: list[Candidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        identity = i3c_signal_identity(item.function)
        if identity is None:
            continue
        pair = pins_by_reference.get(item.reference.casefold(), {})
        data_pins = pair.get((identity.channel, "SDA"), ())
        clock_pins = pair.get((identity.channel, "SCL"), ())
        if len(data_pins) != 1 or len(clock_pins) != 1:
            continue
        inventory = {number.casefold() for number in item.inventory}
        if any(
            pin.rpartition(".")[2].casefold() not in inventory for pin in (*data_pins, *clock_pins)
        ):
            continue

        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{item.pin}: I3C {identity.role} on {item.rail_role} net {item.net_name}"
                ),
                message=(
                    f"The fitted IC I3C {identity.role} function is assigned directly to a net "
                    f"whose label ({item.net_name!r}) is recognized as {item.rail_role}. Review "
                    "whether this assignment is intentional. The function and label are review "
                    "clues, not proof of I3C use, electrical potential, required bus membership, "
                    "or a defect; passive paths and PCB copper are not traced."
                ),
                evidence={
                    "pin": (item.pin,),
                    "pin_function": (item.function,),
                    "i3c_role": (identity.role,),
                    "i3c_channel": (identity.channel or "unindexed",),
                    "assigned_net": (item.net_name,),
                    "net_label_role_clue": (item.rail_role,),
                    "component_pin_inventory": item.inventory,
                },
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
