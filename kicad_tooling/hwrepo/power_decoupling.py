"""Review hints for IC supply rails without a fitted capacitor connection."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_identity import connector_candidate_references, power_function_key
from .models import NetlistContract
from .return_nets import is_return_like_net_name


@dataclass(frozen=True)
class PowerRailCapacitorGap:
    net: str
    input_pins: tuple[str, ...]
    component_references: tuple[str, ...]


def _is_capacitor_symbol(symbol: str) -> bool:
    part = symbol.rsplit(":", 1)[-1].casefold()
    return part in {"c", "cp"} or part.startswith(("c_", "cp_")) or "capacitor" in part


def ic_power_rails_without_fitted_capacitors(
    observed: NetlistContract,
    declared_connector_references: tuple[str, ...] = (),
    mapped_capacitor_references: tuple[str, ...] = (),
) -> tuple[PowerRailCapacitorGap, ...]:
    """Find recognized positive rails with no fitted cap on two distinct nets.

    Pin function and net-name recognition are bounded by ``power_function_key``.
    A capacitor counts only when it connects an IC rail to a distinct net with
    a recognized return-like name or pin function. This remains a review prompt;
    it does not determine datasheet need, capacitance, placement, or a physical
    return path.
    """
    dnp = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_connector_references)
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    capacitor_references = {
        reference.casefold()
        for reference, symbol in observed.component_symbols.items()
        if _is_capacitor_symbol(symbol) and reference.casefold() not in dnp
    }
    capacitor_references.update(
        reference.casefold()
        for reference in mapped_capacitor_references
        if reference.casefold() not in dnp
    )
    capacitor_nets_by_reference: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            reference = pin.rsplit(".", 1)[0].casefold()
            if reference in capacitor_references:
                capacitor_nets_by_reference.setdefault(reference, set()).add(net)
    fitted_capacitor_nets: set[str] = set()
    for assigned_nets in capacitor_nets_by_reference.values():
        return_nets = {
            net
            for net in assigned_nets
            if is_return_like_net_name(net)
            or any(
                is_return_like_net_name(observed.pin_functions.get(pin, ""))
                for pin in observed.nets.get(net, ())
            )
        }
        if return_nets and len(assigned_nets) >= 2:
            fitted_capacitor_nets.update(assigned_nets - return_nets)

    input_pins_by_net: dict[str, set[str]] = {}
    for pin, electrical_type in observed.pin_electrical_types.items():
        if electrical_type.casefold() != "power_in":
            continue
        reference = pin.rsplit(".", 1)[0]
        if (
            reference.startswith("#")
            or reference.casefold() in dnp
            or reference.casefold() in connector_references
        ):
            continue
        assigned_nets = pin_nets.get(pin.casefold(), set())
        if len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        net_pins = observed.nets.get(net, ())
        recognized_positive_rail = power_function_key(net) is not None or any(
            power_function_key(observed.pin_functions.get(net_pin, "")) is not None
            for net_pin in net_pins
        )
        if recognized_positive_rail:
            input_pins_by_net.setdefault(net, set()).add(pin)

    return tuple(
        PowerRailCapacitorGap(
            net=net,
            input_pins=tuple(sorted(pins)),
            component_references=tuple(sorted({pin.rsplit(".", 1)[0] for pin in pins})),
        )
        for net, pins in sorted(input_pins_by_net.items())
        if net not in fitted_capacitor_nets
    )
