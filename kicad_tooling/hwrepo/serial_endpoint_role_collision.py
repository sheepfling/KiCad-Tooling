"""Review same-role UART/USART functions tied directly across an interface."""

from __future__ import annotations

from types import MappingProxyType

from .connector_identity import connector_candidate_references
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index
from .serial_participants import is_serial_ic_reference, serial_function_role_and_channel

RULE_ID: DesignLintRuleId = "bus.serial_endpoint_role_collision"
_ROLE_LABELS = MappingProxyType({"tx": "TX", "rx": "RX"})


def serial_endpoint_role_collision_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Prompt when a connector and IC share a direct same-role serial pin net.

    The check requires exact native serial function roles, complete pin
    inventories, unique direct assignments, and an otherwise two-pin net.
    Same-role wiring can be valid for project-specific interfaces, so this is
    always a review clue unless project policy says otherwise.
    """
    references = {reference.casefold(): reference for reference in observed.components}
    connectors = {reference.casefold() for reference in connector_candidate_references(observed)}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventory = {
        reference.casefold(): {str(number).casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    assignments = netlist_pin_net_index(observed)
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    pins_by_net: dict[str, tuple[str, ...]] = {
        net: tuple(pins) for net, pins in observed.nets.items()
    }
    endpoints_by_net: dict[str, list[tuple[str, str, str, str, str]]] = {}
    serial_pin_counts: dict[str, int] = {}

    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        key = reference.casefold()
        canonical_reference = references.get(key)
        if (
            not separator
            or not number
            or canonical_reference is None
            or key in dnp
            or (key not in connectors and not is_serial_ic_reference(canonical_reference))
            or number.casefold() not in inventory.get(key, set())
        ):
            continue
        identity = serial_function_role_and_channel(function)
        if identity is not None:
            serial_pin_counts[key] = serial_pin_counts.get(key, 0) + 1
        assigned_nets = assignments.get(pin.casefold(), set())
        electrical_type = pin_types.get(pin.casefold())
        if identity is None or len(assigned_nets) != 1 or not electrical_type:
            continue
        net = next(iter(assigned_nets))
        endpoints_by_net.setdefault(net.casefold(), []).append(
            (canonical_reference, pin, identity[0], function, electrical_type)
        )

    findings: list[Candidate] = []
    for net_key, endpoints in sorted(endpoints_by_net.items()):
        if len(endpoints) != 2:
            continue
        left, right = sorted(endpoints, key=lambda item: (item[0].casefold(), item[1].casefold()))
        left_ref, left_pin, left_role, left_function, left_type = left
        right_ref, right_pin, right_role, right_function, right_type = right
        left_key, right_key = left_ref.casefold(), right_ref.casefold()
        if left_key == right_key or left_role != right_role:
            continue
        if serial_pin_counts.get(left_key) != 2 or serial_pin_counts.get(right_key) != 2:
            continue
        if {left_key, right_key} & dnp:
            continue
        if not (
            (left_key in connectors and is_serial_ic_reference(right_ref))
            or (right_key in connectors and is_serial_ic_reference(left_ref))
        ):
            continue
        left_nets = assignments.get(left_pin.casefold(), set())
        right_nets = assignments.get(right_pin.casefold(), set())
        if len(left_nets) != 1 or len(right_nets) != 1:
            continue
        net = next(iter(left_nets))
        if next(iter(right_nets)).casefold() != net_key:
            continue
        exact_net_pins = pins_by_net.get(net, ())
        if len(exact_net_pins) != 2 or {item.casefold() for item in exact_net_pins} != {
            left_pin.casefold(),
            right_pin.casefold(),
        }:
            continue
        if left_type == right_type == "output":
            continue
        connector, controller = (
            (left_ref, right_ref) if left_key in connectors else (right_ref, left_ref)
        )
        role_label = _ROLE_LABELS[left_role]
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{connector}/{controller}: serial {role_label} functions share {net}",
                message=(
                    f"Connector {connector} and serial IC {controller} assign their native "
                    f"{role_label} functions to the same direct net {net}. Review endpoint "
                    "direction and the approved port map; TX/RX labels are role clues and "
                    "do not establish whether this same-role connection is intentional."
                ),
                evidence={
                    "connector": (connector,),
                    "controller": (controller,),
                    "role": (role_label,),
                    "pins": tuple(sorted((left_pin, right_pin), key=str.casefold)),
                    "functions": tuple(sorted((left_function, right_function), key=str.casefold)),
                    "pin_types": tuple(sorted((left_type, right_type))),
                    "net": (net,),
                },
            )
        )
    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
