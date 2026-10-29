"""Review explicit RS-485 A/B pin functions against source net labels."""

from __future__ import annotations

import re

from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .models import NetlistContract
from .rs485_data_functions import explicit_rs485_transceiver_identity
from .rs485_line_functions import rs485_bus_line_role

RULE_ID = "bus.rs485_line_label_mismatch"


def _rs485_net_label_role(net: str) -> str | None:
    """Recognize only unindexed RS-485 A/B labels, not generic A/B names."""
    normalized = re.sub(r"[^a-z0-9]", "", net.casefold())
    if normalized in {"rs485a", "rs485linea"}:
        return "a"
    if normalized in {"rs485b", "rs485lineb"}:
        return "b"
    return None


def rs485_line_label_mismatch_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review fitted RS-485 IC A/B pin assignments that contradict net labels.

    Exact native role functions, explicit transceiver identity, a complete
    two-pin inventory, and unique assignments are required. The finding is a
    naming clue only; project-authored pinout requirements own blocking intent.
    """
    references = {reference.casefold(): reference for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventory = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    roles_by_reference: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        role = rs485_bus_line_role(function)
        if separator and number and role is not None:
            roles_by_reference.setdefault(reference.casefold(), {}).setdefault(role, []).append(
                (pin, number)
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
        known_numbers = inventory.get(reference_key)
        if identity is None or known_numbers is None:
            continue
        pins = {role: roles[role][0] for role in ("a", "b")}
        if any(number.casefold() not in known_numbers for _pin, number in pins.values()):
            continue

        assignments: dict[str, tuple[str, str]] = {}
        for role, (pin, _number) in pins.items():
            assigned_nets = nets_by_pin.get(pin.casefold(), set())
            if len(assigned_nets) != 1:
                break
            net = next(iter(assigned_nets))
            net_role = _rs485_net_label_role(net)
            if net_role is not None:
                assignments[role] = (net, net_role)
        if len(assignments) != 2:
            continue
        if assignments["a"][0].casefold() == assignments["b"][0].casefold():
            continue

        for role in ("a", "b"):
            net, net_role = assignments[role]
            if role == net_role:
                continue
            pin, function = pins[role][0], observed.pin_functions[pins[role][0]]
            findings.append(
                Candidate(
                    rule_id=RULE_ID,
                    subject=f"{pin}: RS-485 {role.upper()} function on {net}",
                    message=(
                        f"The fitted RS-485 transceiver pin function identifies line {role.upper()}, "
                        f"while its assigned net label {net!r} identifies line {net_role.upper()}. "
                        "Review the exact part pinout and interface map; function and net names "
                        "do not establish the required line assignment or physical polarity."
                    ),
                    evidence={
                        "reference": (reference,),
                        "pin": (pin,),
                        "pin_function": (function,),
                        "pin_role": (role,),
                        "net": (net,),
                        "net_role": (net_role,),
                        "identity_basis": (identity,),
                    },
                )
            )
    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
