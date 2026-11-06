"""Review fitted ICs whose MDC and MDIO pins share one net."""

from __future__ import annotations

from .bus_signal_pairs import ethernet_management_function_role
from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

RULE_ID: DesignLintRuleId = "bus.ethernet_management_same_net"


def ethernet_management_same_net_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Find complete, unique MDC/MDIO pairs on one exact native net."""
    roles_by_reference: dict[str, dict[str, list[tuple[str, str, str]]]] = {}
    pin_numbers_by_reference: dict[str, list[str]] = {}
    functions_by_pin: dict[str, list[tuple[str, str]]] = {}

    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        if not separator or not reference or not number:
            continue
        reference_key = reference.casefold()
        pin_key = pin.casefold()
        functions_by_pin.setdefault(pin_key, []).append((pin, function))
        pin_numbers_by_reference.setdefault(reference_key, []).append(number.casefold())
        role = ethernet_management_function_role(function)
        if role is not None:
            roles_by_reference.setdefault(reference_key, {}).setdefault(role, []).append(
                (reference, number, function)
            )

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    nets_by_pin = netlist_pin_net_index(observed)
    pin_types = {
        pin.casefold(): electrical_type.strip().casefold()
        for pin, electrical_type in observed.pin_electrical_types.items()
    }
    findings: list[Candidate] = []

    for reference_key, roles in sorted(roles_by_reference.items()):
        clock_roles = roles.get("clock", ())
        data_roles = roles.get("data", ())
        if len(clock_roles) != 1 or len(data_roles) != 1:
            continue
        reference, clock_number, clock_function = clock_roles[0]
        data_reference, data_number, data_function = data_roles[0]
        if (
            data_reference.casefold() != reference_key
            or not is_integrated_circuit_reference(reference)
            or reference_key in dnp_references
            or lookup_unique_casefold(observed.components, reference) is None
        ):
            continue

        inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
        observed_numbers = pin_numbers_by_reference.get(reference_key, ())
        inventory_numbers = {str(number).casefold() for number in inventory or ()}
        if (
            inventory is None
            or not inventory_numbers
            or len(inventory_numbers) != len(inventory)
            or len(observed_numbers) != len(set(observed_numbers))
            or inventory_numbers != set(observed_numbers)
        ):
            continue

        clock_pin = f"{reference}.{clock_number}"
        data_pin = f"{reference}.{data_number}"
        if (
            len(functions_by_pin.get(clock_pin.casefold(), ())) != 1
            or len(functions_by_pin.get(data_pin.casefold(), ())) != 1
        ):
            continue

        clock_nets = nets_by_pin.get(clock_pin.casefold(), frozenset())
        data_nets = nets_by_pin.get(data_pin.casefold(), frozenset())
        if len(clock_nets) != 1 or len(data_nets) != 1:
            continue
        net = next(iter(clock_nets))
        if net != next(iter(data_nets)):
            continue
        if pin_types.get(clock_pin.casefold()) == pin_types.get(data_pin.casefold()) == "output":
            continue

        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: MDC {clock_pin} and MDIO {data_pin} share {net}",
                message=(
                    f"The exact Ethernet management clock pin {clock_pin} and data pin "
                    f"{data_pin} on {reference} share one schematic net ({net}). Review "
                    "whether the assignment is intentional. Native function names are "
                    "recognition clues; this check does not prove PHY identity or PCB continuity."
                ),
                evidence={
                    "component": (reference,),
                    "MDC_pin": (clock_pin,),
                    "MDC_function": (clock_function,),
                    "MDIO_pin": (data_pin,),
                    "MDIO_function": (data_function,),
                    "MDC_electrical_type": (pin_types.get(clock_pin.casefold(), "unknown"),),
                    "MDIO_electrical_type": (pin_types.get(data_pin.casefold(), "unknown"),),
                    "net": (net,),
                },
            )
        )

    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
