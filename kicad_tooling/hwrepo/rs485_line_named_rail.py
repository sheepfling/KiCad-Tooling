"""Review explicit RS-485 bus-line pins assigned directly to named rails."""

from __future__ import annotations

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .named_rail_pin_evidence import assigned_named_rail_ic_pins
from .rs485_data_functions import explicit_rs485_transceiver_identity
from .rs485_line_functions import rs485_bus_line_role

RULE_ID: DesignLintRuleId = "bus.rs485_line_on_named_rail"


def rs485_line_on_named_rail_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review identified RS-485 A/B pins with one assignment to a named rail.

    Requiring a unique A/B function pair, complete pin inventories, a fitted
    IC, and explicit RS-485 identity keeps generic A/B pins out of scope. The
    rail label remains a clue and the finding defaults to review.
    """
    line_pins_by_reference: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        role = rs485_bus_line_role(function)
        if not separator or not number or role is None:
            continue
        line_pins_by_reference.setdefault(reference.casefold(), {}).setdefault(role, []).append(
            (pin, function)
        )

    candidates: list[Candidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        identity = explicit_rs485_transceiver_identity(observed, item.reference)
        role = rs485_bus_line_role(item.function)
        if identity is None or role is None:
            continue

        pair = line_pins_by_reference.get(item.reference.casefold(), {})
        if len(pair.get("a", ())) != 1 or len(pair.get("b", ())) != 1:
            continue
        line_a, line_b = pair["a"][0], pair["b"][0]
        known_numbers = {number.casefold() for number in item.inventory}
        if any(
            pin.rpartition(".")[2].casefold() not in known_numbers
            for pin, _function in (line_a, line_b)
        ):
            continue

        peer_pin, peer_function = line_b if role == "a" else line_a
        role_name = "A" if role == "a" else "B"
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The identified RS-485 bus-line {role_name} function is assigned to a "
                    f"net whose label ({item.net_name!r}) is recognized as {item.rail_role}. "
                    "Review whether this direct assignment is intentional. Identity, function, "
                    "and label are review clues, not proof of electrical potential, a required "
                    "bus topology, a defect, PCB copper, or physical continuity."
                ),
                evidence={
                    "pin": (item.pin,),
                    "pin_function": (item.function,),
                    "rs485_line_role": (role,),
                    "complementary_line_pin": (peer_pin,),
                    "complementary_line_function": (peer_function,),
                    "assigned_net": (item.net_name,),
                    "net_label_role_clue": (item.rail_role,),
                    "identity_basis": (identity,),
                    "component_pin_inventory": item.inventory,
                },
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
