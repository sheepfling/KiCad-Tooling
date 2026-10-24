"""Review open RS-485 D/DI or R/RO pins beside an assigned counterpart."""

from __future__ import annotations

from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .models import NetlistContract
from .rs485_data_functions import explicit_rs485_transceiver_identity, rs485_data_pin_role

RULE_ID = "bus.rs485_unconnected_data_pin"


def rs485_unconnected_data_pin_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Prompt when one explicit RS-485 data role is open beside an assigned role.

    This defaults to a project-configurable review clue because a transceiver
    may intentionally be used in a one-way mode. Complete native pin metadata,
    an explicit device identity, and unique assignments keep the inference
    narrow; none of them proves the interface is required or used.
    """
    references = {reference.casefold(): reference for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)

    functions_by_reference: dict[str, list[tuple[str, str, str]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        if separator and reference and number:
            functions_by_reference.setdefault(reference.casefold(), []).append(
                (pin, number, function)
            )

    findings: list[Candidate] = []
    for folded_reference, functions in sorted(functions_by_reference.items()):
        reference = references.get(folded_reference)
        if (
            reference is None
            or folded_reference in dnp
            or not is_integrated_circuit_reference(reference)
        ):
            continue

        identity = explicit_rs485_transceiver_identity(observed, reference)
        if identity is None:
            continue

        inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
        function_numbers = tuple(number.casefold() for _, number, _ in functions)
        if (
            inventory is None
            or not inventory
            or len({number.casefold() for number in inventory}) != len(inventory)
            or len(set(function_numbers)) != len(function_numbers)
            or set(function_numbers) != {number.casefold() for number in inventory}
        ):
            continue

        role_pins: dict[str, list[tuple[str, str]]] = {"tx": [], "rx": []}
        for pin, _number, function in functions:
            role = rs485_data_pin_role(function)
            if role is not None:
                role_pins[role].append((pin, function))
        if len(role_pins["tx"]) != 1 or len(role_pins["rx"]) != 1:
            continue

        tx_pin, tx_function = role_pins["tx"][0]
        rx_pin, rx_function = role_pins["rx"][0]
        tx_nets = assignments.get(tx_pin.casefold(), set())
        rx_nets = assignments.get(rx_pin.casefold(), set())
        if len(tx_nets) == 1 and not rx_nets:
            open_pin, open_function, open_role = rx_pin, rx_function, "receiver-output"
            paired_pin, paired_function, paired_role = tx_pin, tx_function, "driver-input"
            paired_net = next(iter(tx_nets))
        elif len(rx_nets) == 1 and not tx_nets:
            open_pin, open_function, open_role = tx_pin, tx_function, "driver-input"
            paired_pin, paired_function, paired_role = rx_pin, rx_function, "receiver-output"
            paired_net = next(iter(rx_nets))
        else:
            continue

        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{open_pin}: {open_function}",
                message=(
                    f"This RS-485 {open_role} pin has no net assignment while its paired "
                    f"{paired_role} pin {paired_pin} is assigned to {paired_net}. Review "
                    "whether one-way operation is intentional or a connection is missing; "
                    "pin functions do not establish interface use or PCB routing."
                ),
                evidence={
                    open_pin: (),
                    "function": (open_function,),
                    "rs485_data_role": (open_role,),
                    "paired_pin": (paired_pin,),
                    "paired_function": (paired_function,),
                    "paired_role": (paired_role,),
                    "paired_net": (paired_net,),
                    "identity_basis": (identity,),
                },
            )
        )
    return tuple(findings)
