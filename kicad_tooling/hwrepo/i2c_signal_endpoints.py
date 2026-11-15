"""Bounded fitted IC SDA/SCL endpoints used by I2C signal checks."""

from __future__ import annotations

from dataclasses import dataclass

from .component_references import is_integrated_circuit_reference
from .i2c_addressing import i2c_signal_role
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index


@dataclass(frozen=True, slots=True)
class I2cSignalEndpoint:
    """One fitted IC with one native SDA pin and one native SCL pin."""

    reference: str
    sda_pin: str
    scl_pin: str
    sda_net: str
    scl_net: str
    sda_type: str
    scl_type: str


def i2c_signal_endpoints(observed: NetlistContract) -> tuple[I2cSignalEndpoint, ...]:
    """Return complete, uniquely assigned SDA/SCL pairs on fitted U/IC parts.

    Bounded native function aliases are clues only. Open, multiply assigned,
    duplicate-role, DNP, and inventory-inconsistent components are omitted.
    The two pins may share a net; consumers decide which topology they review.
    """
    fitted = {
        reference.casefold(): reference
        for reference in observed.components
        if is_integrated_circuit_reference(reference)
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventories = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    nets_by_pin = netlist_pin_net_index(observed)
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    roles_by_reference: dict[str, dict[str, list[tuple[str, tuple[str, ...]]]]] = {}
    invalid_references: set[str] = set()
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        canonical_reference = fitted.get(reference_key)
        role = i2c_signal_role(function)
        if not separator or canonical_reference is None or role is None:
            continue
        inventory = inventories.get(reference_key, set())
        if not inventory or number.casefold() not in inventory:
            invalid_references.add(reference_key)
            continue
        assignments = tuple(
            sorted(nets_by_pin.get(pin.casefold(), ()), key=lambda item: (item.casefold(), item))
        )
        roles_by_reference.setdefault(reference_key, {}).setdefault(role, []).append(
            (f"{canonical_reference}.{number}", assignments)
        )

    endpoints: list[I2cSignalEndpoint] = []
    for reference_key, roles in sorted(roles_by_reference.items()):
        if reference_key in dnp or reference_key in invalid_references:
            continue
        sda_pins = roles.get("SDA", ())
        scl_pins = roles.get("SCL", ())
        if len(sda_pins) != 1 or len(scl_pins) != 1:
            continue
        sda_pin, sda_assignments = sda_pins[0]
        scl_pin, scl_assignments = scl_pins[0]
        if len(sda_assignments) != 1 or len(scl_assignments) != 1:
            continue
        endpoints.append(
            I2cSignalEndpoint(
                reference=fitted[reference_key],
                sda_pin=sda_pin,
                scl_pin=scl_pin,
                sda_net=sda_assignments[0],
                scl_net=scl_assignments[0],
                sda_type=pin_types.get(sda_pin.casefold(), "unknown"),
                scl_type=pin_types.get(scl_pin.casefold(), "unknown"),
            )
        )
    return tuple(sorted(endpoints, key=lambda item: (item.reference.casefold(), item.reference)))
