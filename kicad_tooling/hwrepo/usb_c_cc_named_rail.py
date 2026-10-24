"""Review fitted USB-C CC controller pins assigned directly to named rails."""

from __future__ import annotations

from .bus_signal_roles import usb_c_cc_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .named_rail_pin_evidence import assigned_named_rail_ic_pins

RULE_ID: DesignLintRuleId = "bus.usb_c_cc_signal_on_named_rail"


def usb_c_cc_signal_on_named_rail_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review unique fitted IC CC1/CC2 functions on supply/return-like labels.

    The exact CC role, fitted U/IC reference, complete pin inventory, and
    unambiguous direct rail assignment are review clues. A matching name does
    not establish the USB-C port role or the electrical requirement.
    """
    cc_roles_by_reference: dict[str, dict[str, list[str]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        role = usb_c_cc_role(function)
        if not separator or not number or role is None:
            continue
        cc_roles_by_reference.setdefault(reference.casefold(), {}).setdefault(role, []).append(
            pin
        )

    candidates: list[Candidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        role = usb_c_cc_role(item.function)
        if role is None:
            continue
        pair = cc_roles_by_reference.get(item.reference.casefold(), {})
        if any(len(pair.get(pair_role, ())) != 1 for pair_role in ("CC1", "CC2")):
            continue
        inventory = {number.casefold() for number in item.inventory}
        if any(
            pin.rpartition(".")[2].casefold() not in inventory
            for pair_pins in pair.values()
            for pin in pair_pins
        ):
            continue

        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{item.pin}: {role} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The fitted IC USB-C {role} function is assigned to a net whose label "
                    f"({item.net_name!r}) is recognized as {item.rail_role}. Review whether "
                    "this direct assignment is intentional. Function and label are review "
                    "clues, not proof of electrical potential, port role, Rp/Rd requirements, "
                    "or a defect; this check does not trace passive paths or assess PCB copper "
                    "or physical continuity."
                ),
                evidence={
                    "pin": (item.pin,),
                    "pin_function": (item.function,),
                    "usb_c_cc_role": (role,),
                    "assigned_net": (item.net_name,),
                    "net_label_role_clue": (item.rail_role,),
                    "component_pin_inventory": item.inventory,
                },
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
