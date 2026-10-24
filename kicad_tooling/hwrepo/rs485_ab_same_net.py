"""Review explicit RS-485 transceiver A/B line pins assigned to one net."""

from __future__ import annotations

from .component_references import is_integrated_circuit_reference
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index
from .rs485_data_functions import explicit_rs485_transceiver_identity
from .rs485_line_functions import rs485_bus_line_role

RULE_ID: DesignLintRuleId = "bus.rs485_ab_same_net"


def rs485_ab_same_net_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review one explicit RS-485 A/B pin pair assigned to the same net.

    The predicate requires a fitted, explicitly identified U/IC reference,
    exactly one A and B function, both functions in the native pin inventory,
    and one exact assignment per pin. Native ERC owns two-output conflicts.
    """
    references = {reference.casefold(): reference for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventory_by_reference = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    assignments_by_pin = netlist_pin_net_index(observed)
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }

    roles_by_reference: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        role = rs485_bus_line_role(function)
        if not separator or not number or role is None:
            continue
        roles_by_reference.setdefault(reference.casefold(), {}).setdefault(role, []).append(
            (pin, function)
        )

    findings: list[Candidate] = []
    for reference_key, roles in sorted(roles_by_reference.items()):
        reference = references.get(reference_key)
        if (
            reference is None
            or reference_key in dnp
            or not is_integrated_circuit_reference(reference)
            or len(roles.get("a", ())) != 1
            or len(roles.get("b", ())) != 1
        ):
            continue

        identity = explicit_rs485_transceiver_identity(observed, reference)
        if identity is None:
            continue

        inventory = inventory_by_reference.get(reference_key)
        if inventory is None:
            continue
        pin_a, function_a = roles["a"][0]
        pin_b, function_b = roles["b"][0]
        if any(
            number.casefold() not in inventory
            for number in (pin_a.rpartition(".")[2], pin_b.rpartition(".")[2])
        ):
            continue

        assignments_a = assignments_by_pin.get(pin_a.casefold(), set())
        assignments_b = assignments_by_pin.get(pin_b.casefold(), set())
        if len(assignments_a) != 1 or len(assignments_b) != 1:
            continue
        net_a, net_b = next(iter(assignments_a)), next(iter(assignments_b))
        if net_a != net_b:
            continue
        if pin_types.get(pin_a.casefold()) == pin_types.get(pin_b.casefold()) == "output":
            continue

        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: RS-485 A/B bus pins share {net_a}",
                message=(
                    f"Explicitly identified RS-485 IC {reference} has A pin {pin_a} "
                    f"({function_a}) and B pin {pin_b} ({function_b}) on one schematic "
                    f"net ({net_a}). Review whether the shared assignment is intentional. "
                    "Native symbol identity and function names are recognition clues; this "
                    "heuristic does not establish the exact part pinout or intended topology."
                ),
                evidence={
                    "component": (reference,),
                    "A_pin": (pin_a,),
                    "A_function": (function_a,),
                    "B_pin": (pin_b,),
                    "B_function": (function_b,),
                    "net": (net_a,),
                    "identity_basis": (identity,),
                },
            )
        )
    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
