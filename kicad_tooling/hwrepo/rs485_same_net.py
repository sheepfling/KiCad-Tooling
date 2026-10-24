"""Review fitted RS-485 transceiver data-input and data-output pins on one net."""

from __future__ import annotations

from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index
from .rs485_data_functions import explicit_rs485_transceiver_identity, rs485_data_pin_role

RULE_ID = "bus.rs485_data_input_output_same_net"


def rs485_data_input_output_same_net_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review one explicit RS-485 D/DI and R/RO pair assigned to the same net.

    Component identity must explicitly identify an RS-485 device. The rule also
    requires a complete native pin inventory, one role pin per direction, and
    unique assignments. It is a configurable review clue because echo and
    single-wire operation can intentionally join these pins.
    """
    references = {reference.casefold(): reference for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    nets_by_pin = netlist_pin_net_index(observed)

    roles_by_reference: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        role = rs485_data_pin_role(function)
        if not separator or not number or role is None:
            continue
        roles_by_reference.setdefault(reference.casefold(), {}).setdefault(role, []).append(
            (pin, number)
        )

    electrical_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    findings: list[Candidate] = []
    for folded_reference, roles in sorted(roles_by_reference.items()):
        reference = references.get(folded_reference)
        if (
            reference is None
            or folded_reference in dnp
            or not is_integrated_circuit_reference(reference)
            or len(roles.get("tx", ())) != 1
            or len(roles.get("rx", ())) != 1
        ):
            continue

        identity = explicit_rs485_transceiver_identity(observed, reference)
        if identity is None:
            continue

        inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
        if inventory is None:
            continue
        known_numbers = {item.casefold() for item in inventory}
        data_pins = {role: roles[role][0] for role in ("tx", "rx")}
        if any(number.casefold() not in known_numbers for _pin, number in data_pins.values()):
            continue

        assignments: dict[str, str] = {}
        for role, (pin, _number) in data_pins.items():
            assigned_nets = nets_by_pin.get(pin.casefold(), set())
            if len(assigned_nets) != 1:
                break
            assignments[role] = next(iter(assigned_nets))
        if set(assignments) != {"tx", "rx"}:
            continue
        if assignments["tx"] != assignments["rx"]:
            continue

        driver_pin = data_pins["tx"][0]
        receiver_pin = data_pins["rx"][0]
        driver_type = electrical_types.get(driver_pin.casefold(), "unknown")
        receiver_type = electrical_types.get(receiver_pin.casefold(), "unknown")
        if driver_type == receiver_type == "output":
            continue

        net = assignments["tx"]
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: RS-485 driver input and receiver output share {net}",
                message=(
                    f"Fitted RS-485 IC {reference} has driver-data input {driver_pin} "
                    f"({observed.pin_functions[driver_pin]}, {driver_type}) and receiver-data "
                    f"output {receiver_pin} ({observed.pin_functions[receiver_pin]}, "
                    f"{receiver_type}) on one schematic net ({net}). Review whether this is "
                    "intentional echo or single-wire operation, or a pin-assignment mistake; "
                    "the heuristic does not establish required topology."
                ),
                evidence={
                    "component": (reference,),
                    "driver_input_pin": (driver_pin,),
                    "driver_input_function": (observed.pin_functions[driver_pin],),
                    "driver_input_electrical_type": (driver_type,),
                    "receiver_output_pin": (receiver_pin,),
                    "receiver_output_function": (observed.pin_functions[receiver_pin],),
                    "receiver_output_electrical_type": (receiver_type,),
                    "net": (net,),
                    "identity_basis": (identity,),
                },
            )
        )
    return tuple(findings)
