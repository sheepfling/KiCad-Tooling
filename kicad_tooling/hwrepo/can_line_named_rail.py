"""Review CAN transceiver bus-line pins assigned directly to named rails."""

from __future__ import annotations

from .bus_signal_roles import can_function_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .named_rail_pin_evidence import assigned_named_rail_ic_pins

RULE_ID: DesignLintRuleId = "bus.can_line_on_named_rail"


def can_line_on_named_rail_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review fitted IC CANH/CANL pins assigned to supply- or return-like labels.

    A unique exported CANH/CANL function pair and complete native inventory
    distinguish bus-side pins from controller TX/RX signals. The assignment
    and rail-like name remain review clues, not proof of a defect.
    """
    line_pins_by_reference: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        role = can_function_role(function)
        if not separator or not number or role not in {"CANH", "CANL"}:
            continue
        line_pins_by_reference.setdefault(reference.casefold(), {}).setdefault(role, []).append(
            (pin, function)
        )

    candidates: list[Candidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        role = can_function_role(item.function)
        if role not in {"CANH", "CANL"}:
            continue

        pair = line_pins_by_reference.get(item.reference.casefold(), {})
        if len(pair.get("CANH", ())) != 1 or len(pair.get("CANL", ())) != 1:
            continue
        line_high, line_low = pair["CANH"][0], pair["CANL"][0]
        known_numbers = {number.casefold() for number in item.inventory}
        if any(
            pin.rpartition(".")[2].casefold() not in known_numbers
            for pin, _function in (line_high, line_low)
        ):
            continue

        peer_pin, peer_function = line_low if role == "CANH" else line_high
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The CAN bus-line {role} function is assigned to a net whose label "
                    f"({item.net_name!r}) is recognized as {item.rail_role}. Review whether "
                    "this direct assignment is intentional. Function and label are review "
                    "clues, not proof of electrical potential, required CAN connectivity, or "
                    "a defect; this check does not assess PCB copper or physical continuity."
                ),
                evidence={
                    "pin": (item.pin,),
                    "pin_function": (item.function,),
                    "can_line_role": (role,),
                    "complementary_line_pin": (peer_pin,),
                    "complementary_line_function": (peer_function,),
                    "assigned_net": (item.net_name,),
                    "net_label_role_clue": (item.rail_role,),
                    "component_pin_inventory": item.inventory,
                },
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
