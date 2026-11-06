"""Review likely USB-C ports without a recognized VBUS-to-return capacitor."""

from __future__ import annotations

from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from .bus_signal_roles import usb_c_cc_role
from .capacitor_symbols import is_capacitor_symbol
from .casefold_mapping_lookup import lookup_unique_casefold
from .connector_identity import (
    connector_candidate_references,
    connector_power_function_key,
    is_return_function,
)
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import NetlistPinNetIndex, netlist_pin_net_index
from .usb_c_ports import UsbCPortRosterContext


@dataclass(frozen=True, slots=True)
class UsbCVbusCapacitanceGap:
    """Native connector evidence for a likely USB-C port VBUS review."""

    connector: str
    cc1_pins: tuple[str, ...]
    cc2_pins: tuple[str, ...]
    vbus_pin_assignments: tuple[tuple[str, str], ...]
    return_pin_assignments: tuple[tuple[str, str], ...]
    vbus_net: str
    return_net: str
    capacitor_touchpoints: tuple[str, ...]
    review_scope: str
    electrical_contract_path: str | None = None
    electrical_contract_sha256: str | None = None


def usb_c_vbus_capacitance_gaps(
    observed: NetlistContract,
    roster: UsbCPortRosterContext,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[UsbCVbusCapacitanceGap, ...]:
    """Find likely USB-C ports with no fitted, exact two-pin cap across VBUS/return.

    The pin functions and symbol identities create a review candidate only. A
    current project port map that requires or explicitly excludes the
    capacitance scope owns that decision and suppresses this heuristic.
    """
    components = {reference.casefold(): reference for reference in observed.components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_connector_references)
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventories = {
        reference.casefold(): tuple(number.casefold() for number in numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    assignments = netlist_pin_net_index(observed)
    cap_scope_by_connector = _capacitance_scopes(roster)

    roles_by_connector: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        if not separator or not number:
            continue
        role = usb_c_cc_role(function)
        if role is None and connector_power_function_key(function) == "vbus":
            role = "VBUS"
        elif role is None and is_return_function(function):
            role = "RETURN"
        if role is not None:
            roles_by_connector.setdefault(reference.casefold(), {}).setdefault(role, []).append(
                (pin, function)
            )

    gaps: list[UsbCVbusCapacitanceGap] = []
    for reference_key, roles in sorted(roles_by_connector.items()):
        reference = components.get(reference_key)
        if (
            reference is None
            or reference_key not in connector_references
            or reference_key in dnp
            or len(roles.get("CC1", ())) != 1
            or len(roles.get("CC2", ())) != 1
            or not roles.get("VBUS")
            or not roles.get("RETURN")
        ):
            continue

        scope = cap_scope_by_connector.get(reference_key)
        if scope in {"required", "not_applicable"}:
            continue

        inventory = inventories.get(reference_key)
        if inventory is None or len(set(inventory)) != len(inventory):
            continue
        role_pins = tuple(
            pin
            for role in ("CC1", "CC2", "VBUS", "RETURN")
            for pin, _function in roles.get(role, ())
        )
        if any(pin.rpartition(".")[2].casefold() not in inventory for pin in role_pins):
            continue

        cc1_pins = tuple(sorted((pin for pin, _ in roles["CC1"]), key=str.casefold))
        cc2_pins = tuple(sorted((pin for pin, _ in roles["CC2"]), key=str.casefold))
        vbus_pin_assignments = _single_net_pin_assignments(roles["VBUS"], assignments)
        return_pin_assignments = _single_net_pin_assignments(roles["RETURN"], assignments)
        if not vbus_pin_assignments or not return_pin_assignments:
            continue
        vbus_nets = {net for _pin, net in vbus_pin_assignments}
        return_nets = {net for _pin, net in return_pin_assignments}
        if len(vbus_nets) != 1 or len(return_nets) != 1:
            continue
        vbus_net = next(iter(vbus_nets))
        return_net = next(iter(return_nets))
        if vbus_net == return_net or _has_fitted_capacitor(
            observed, assignments, vbus_net, return_net
        ):
            continue

        gaps.append(
            UsbCVbusCapacitanceGap(
                connector=reference,
                cc1_pins=cc1_pins,
                cc2_pins=cc2_pins,
                vbus_pin_assignments=vbus_pin_assignments,
                return_pin_assignments=return_pin_assignments,
                vbus_net=vbus_net,
                return_net=return_net,
                capacitor_touchpoints=_capacitor_touchpoints(
                    observed, assignments, {vbus_net, return_net}
                ),
                review_scope=scope or roster.state,
                electrical_contract_path=roster.source_path,
                electrical_contract_sha256=roster.source_sha256,
            )
        )
    return tuple(gaps)


def _capacitance_scopes(roster: UsbCPortRosterContext) -> dict[str, str]:
    if roster.analysis is None:
        return {}
    return {port.connector.casefold(): port.vbus_capacitance.mode for port in roster.analysis.ports}


def _single_net_pin_assignments(
    role_pins: Sequence[tuple[str, str]], assignments: NetlistPinNetIndex
) -> tuple[tuple[str, str], ...]:
    if not all(len(assignments.get(pin.casefold(), ())) == 1 for pin, _ in role_pins):
        return ()
    return tuple(
        sorted(
            ((pin, next(iter(assignments[pin.casefold()]))) for pin, _function in role_pins),
            key=lambda item: (item[0].casefold(), item[1].casefold()),
        )
    )


def _has_fitted_capacitor(
    observed: NetlistContract,
    assignments: NetlistPinNetIndex,
    vbus_net: str,
    return_net: str,
) -> bool:
    dnp = {reference.casefold() for reference in observed.dnp_components}
    for reference, symbol in observed.component_symbols.items():
        reference_key = reference.casefold()
        if reference_key in dnp or not is_capacitor_symbol(symbol):
            continue
        pin_numbers = lookup_unique_casefold(observed.component_pin_numbers, reference)
        if pin_numbers is None or len(pin_numbers) != 2:
            continue
        folded_numbers = tuple(number.casefold() for number in pin_numbers)
        if len(set(folded_numbers)) != 2:
            continue
        pin_nets = tuple(
            assignments.get(f"{reference}.{number}".casefold(), ()) for number in pin_numbers
        )
        if any(len(nets) != 1 for nets in pin_nets):
            continue
        if {next(iter(nets)) for nets in pin_nets} == {vbus_net, return_net}:
            return True
    return False


def _capacitor_touchpoints(
    observed: NetlistContract,
    assignments: NetlistPinNetIndex,
    port_nets: AbstractSet[str],
) -> tuple[str, ...]:
    dnp = {reference.casefold() for reference in observed.dnp_components}
    touching: list[str] = []
    for reference, symbol in observed.component_symbols.items():
        if not is_capacitor_symbol(symbol):
            continue
        pin_numbers = lookup_unique_casefold(observed.component_pin_numbers, reference)
        if pin_numbers is None:
            continue
        assigned = tuple(
            sorted(
                {
                    net
                    for number in pin_numbers
                    for net in assignments.get(f"{reference}.{number}".casefold(), ())
                },
                key=lambda net: (net.casefold(), net),
            )
        )
        if not any(net in port_nets for net in assigned):
            continue
        population = "DNP" if reference.casefold() in dnp else "fitted"
        touching.append(f"{reference} ({population})={'/'.join(assigned) or 'unassigned'}")
    return tuple(sorted(touching, key=lambda item: (item.casefold(), item)))
