"""Recognize generic connector contacts assigned to USB-C controller CC nets."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from .bus_signal_roles import usb_c_cc_role
from .casefold_mapping_lookup import casefolded_unique_index
from .connector_contact_evidence import ConnectorContactEvidence, collect_other_connector_contacts
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import NetlistPinNetIndex, netlist_pin_net_index

_CONTROLLER_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class UsbCGenericConnectorPair:
    """Native generic connector contacts on one controller's distinct CC nets."""

    connector_reference: str
    controller_reference: str
    controller_cc1_pin: str
    controller_cc1_function: str
    cc1_net: str
    connector_cc1_pins: tuple[str, ...]
    connector_cc1_functions: tuple[str, ...]
    controller_cc2_pin: str
    controller_cc2_function: str
    cc2_net: str
    connector_cc2_pins: tuple[str, ...]
    connector_cc2_functions: tuple[str, ...]
    connector_pin_count: int
    other_connector_contacts: tuple[ConnectorContactEvidence, ...] = ()


@dataclass(frozen=True, slots=True)
class _ControllerPair:
    reference: str
    cc1_pin: str
    cc1_function: str
    cc1_net: str
    cc2_pin: str
    cc2_function: str
    cc2_net: str


def usb_c_generic_connector_pairs(
    observed: NetlistContract,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[UsbCGenericConnectorPair, ...]:
    """Return only unique, complete, direct-net controller/connector matches.

    Native CC function names on a fitted U/IC and generic Pin_N connector
    functions establish a review candidate. They do not identify a USB-C
    receptacle, prove an interface, or establish an electrical requirement.
    """
    references = casefolded_unique_index(
        {reference: reference for reference in observed.components}
    )
    symbols = casefolded_unique_index(observed.component_symbols)
    inventories = casefolded_unique_index(observed.component_pin_numbers)
    functions = casefolded_unique_index(observed.pin_functions)
    assignments = netlist_pin_net_index(observed)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    function_numbers = _component_function_numbers(observed)
    controllers = _controller_pairs(
        observed,
        references,
        inventories,
        functions,
        function_numbers,
        assignments,
        dnp,
    )
    if not controllers:
        return ()

    connectors: list[tuple[str, tuple[str, ...], dict[str, str]]] = []
    for reference in connector_candidate_references(observed, declared_connector_references):
        key = reference.casefold()
        canonical = references.get(key)
        inventory = inventories.get(key)
        if canonical is None or key in dnp or key not in symbols or inventory is None:
            continue
        if not _complete_inventory(canonical, inventory, functions, function_numbers):
            continue
        pin_functions: dict[str, str] = {}
        complete = True
        for number in inventory:
            pin = f"{canonical}.{number}"
            function = functions.get(pin.casefold())
            if function is None:
                complete = False
                break
            pin_functions[pin] = function
        if complete:
            connectors.append((canonical, inventory, pin_functions))

    findings: list[UsbCGenericConnectorPair] = []
    for connector, inventory, pin_functions in connectors:
        generic_by_net: dict[str, list[tuple[str, str]]] = {}
        for pin, function in pin_functions.items():
            if not pin_function_is_generic(function):
                continue
            pin_nets = assignments.get(pin.casefold(), frozenset())
            if len(pin_nets) != 1:
                continue
            net = next(iter(pin_nets))
            generic_by_net.setdefault(net, []).append((pin, function))

        matching = [
            controller
            for controller in controllers
            if controller.cc1_net in generic_by_net and controller.cc2_net in generic_by_net
        ]
        if len(matching) != 1:
            continue
        controller = matching[0]
        cc1_contacts = tuple(sorted(generic_by_net[controller.cc1_net], key=_contact_key))
        cc2_contacts = tuple(sorted(generic_by_net[controller.cc2_net], key=_contact_key))
        findings.append(
            UsbCGenericConnectorPair(
                connector_reference=connector,
                controller_reference=controller.reference,
                controller_cc1_pin=controller.cc1_pin,
                controller_cc1_function=controller.cc1_function,
                cc1_net=controller.cc1_net,
                connector_cc1_pins=tuple(pin for pin, _function in cc1_contacts),
                connector_cc1_functions=tuple(function for _pin, function in cc1_contacts),
                controller_cc2_pin=controller.cc2_pin,
                controller_cc2_function=controller.cc2_function,
                cc2_net=controller.cc2_net,
                connector_cc2_pins=tuple(pin for pin, _function in cc2_contacts),
                connector_cc2_functions=tuple(function for _pin, function in cc2_contacts),
                connector_pin_count=len(inventory),
                other_connector_contacts=collect_other_connector_contacts(
                    connector,
                    inventory,
                    tuple(pin_functions[f"{connector}.{number}"] for number in inventory),
                    assignments,
                    (
                        *(pin for pin, _function in cc1_contacts),
                        *(pin for pin, _function in cc2_contacts),
                    ),
                ),
            )
        )
    return tuple(
        sorted(
            findings,
            key=lambda pair: (
                pair.connector_reference.casefold(),
                pair.controller_reference.casefold(),
            ),
        )
    )


def _controller_pairs(
    observed: NetlistContract,
    references: Mapping[str, str],
    inventories: Mapping[str, tuple[str, ...]],
    functions: Mapping[str, str],
    function_numbers: Mapping[str, tuple[str, ...]],
    assignments: NetlistPinNetIndex,
    dnp: set[str],
) -> tuple[_ControllerPair, ...]:
    fitted = {
        key: reference
        for key, reference in references.items()
        if _CONTROLLER_REFERENCE.fullmatch(reference) and key not in dnp
    }
    roles: dict[str, dict[str, list[tuple[str, str]]]] = {}
    invalid: set[str] = set()
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        key = reference.casefold()
        role = usb_c_cc_role(function)
        if not separator or key not in fitted or role is None:
            continue
        inventory = inventories.get(key)
        if inventory is None or number.casefold() not in {item.casefold() for item in inventory}:
            invalid.add(key)
            continue
        roles.setdefault(key, {}).setdefault(role, []).append((pin, function))

    result: list[_ControllerPair] = []
    electrical_types = casefolded_unique_index(observed.pin_electrical_types)
    for key, component_roles in roles.items():
        inventory = inventories.get(key)
        reference = fitted[key]
        if (
            key in invalid
            or key in dnp
            or inventory is None
            or not _complete_inventory(reference, inventory, functions, function_numbers)
        ):
            continue
        cc1, cc2 = component_roles.get("CC1", ()), component_roles.get("CC2", ())
        if len(cc1) != 1 or len(cc2) != 1:
            continue
        cc1_pin, cc1_function = cc1[0]
        cc2_pin, cc2_function = cc2[0]
        cc1_nets = assignments.get(cc1_pin.casefold(), frozenset())
        cc2_nets = assignments.get(cc2_pin.casefold(), frozenset())
        if len(cc1_nets) != 1 or len(cc2_nets) != 1 or cc1_nets == cc2_nets:
            continue
        cc1_type = electrical_types.get(cc1_pin.casefold(), "").strip().casefold()
        cc2_type = electrical_types.get(cc2_pin.casefold(), "").strip().casefold()
        if cc1_type == cc2_type == "output":
            continue
        result.append(
            _ControllerPair(
                reference=fitted[key],
                cc1_pin=cc1_pin,
                cc1_function=cc1_function,
                cc1_net=next(iter(cc1_nets)),
                cc2_pin=cc2_pin,
                cc2_function=cc2_function,
                cc2_net=next(iter(cc2_nets)),
            )
        )
    return tuple(result)


def _component_function_numbers(observed: NetlistContract) -> Mapping[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for pin in observed.pin_functions:
        reference, separator, number = pin.rpartition(".")
        if separator:
            grouped.setdefault(reference.casefold(), []).append(number)
    return {reference: tuple(numbers) for reference, numbers in grouped.items()}


def _complete_inventory(
    reference: str,
    inventory: tuple[str, ...],
    functions: Mapping[str, str],
    function_numbers: Mapping[str, tuple[str, ...]],
) -> bool:
    """Require a unique pin inventory fully represented by native pin functions."""
    numbers = tuple(number.casefold() for number in inventory)
    represented = tuple(
        number.casefold() for number in function_numbers.get(reference.casefold(), ())
    )
    return (
        bool(numbers)
        and len(set(numbers)) == len(numbers)
        and len(set(represented)) == len(represented)
        and set(numbers) == set(represented)
        and all(f"{reference}.{number}".casefold() in functions for number in inventory)
    )


def _contact_key(contact: tuple[str, str]) -> tuple[str, str]:
    return contact[0].casefold(), contact[0]
