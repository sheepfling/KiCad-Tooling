"""Review fitted I2C SDA/SCL pin pairs that share one schematic net."""

from __future__ import annotations

import re

from .design_lint_types import Candidate
from .i2c_addressing import i2c_signal_role
from .models import NetlistContract

RULE_ID = "bus.i2c_sda_scl_same_net"
_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


def i2c_sda_scl_same_net_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find fitted ICs with one uniquely assigned native SDA/SCL pair on one net.

    The check uses the bounded I2C function aliases shared by other I2C checks.
    It requires both role pins to occur in the exported component pin inventory
    and excludes ambiguous, open, DNP, and multi-port cases.
    """
    fitted = {
        reference.casefold(): reference
        for reference in observed.components
        if _IC_REFERENCE.fullmatch(reference)
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_numbers = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }

    roles_by_reference: dict[str, dict[str, list[tuple[str, tuple[str, ...]]]]] = {}
    invalid_inventory_references: set[str] = set()
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        canonical_reference = fitted.get(reference_key)
        role = i2c_signal_role(function)
        if not separator or canonical_reference is None or role is None:
            continue
        inventory = pin_numbers.get(reference_key, set())
        if not inventory or number.casefold() not in inventory:
            invalid_inventory_references.add(reference_key)
            continue
        assignments = tuple(
            sorted(nets_by_pin.get(pin.casefold(), ()), key=lambda item: (item.casefold(), item))
        )
        roles_by_reference.setdefault(reference_key, {}).setdefault(role, []).append(
            (f"{canonical_reference}.{number}", assignments)
        )

    findings: list[Candidate] = []
    for reference_key, roles in sorted(roles_by_reference.items()):
        if reference_key in dnp or reference_key in invalid_inventory_references:
            continue
        sda_pins = roles.get("SDA", ())
        scl_pins = roles.get("SCL", ())
        if len(sda_pins) != 1 or len(scl_pins) != 1:
            continue
        sda_pin, sda_assignments = sda_pins[0]
        scl_pin, scl_assignments = scl_pins[0]
        if len(sda_assignments) != 1 or len(scl_assignments) != 1:
            continue
        sda_net = sda_assignments[0]
        scl_net = scl_assignments[0]
        if sda_net.casefold() != scl_net.casefold() or sda_net != scl_net:
            continue
        if pin_types.get(sda_pin.casefold()) == pin_types.get(scl_pin.casefold()) == "output":
            continue

        reference = fitted[reference_key]
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: I2C SDA/SCL pins share {sda_net}",
                message=(
                    f"The bounded native I2C SDA pin {sda_pin} and SCL pin {scl_pin} on "
                    f"{reference} share one schematic net ({sda_net}). Review whether this "
                    "is intentional. Function names are clues only; this check does not prove "
                    "the part implements standard I2C or establish the intended topology."
                ),
                evidence={
                    "component": (reference,),
                    "SDA_pin": (sda_pin,),
                    "SCL_pin": (scl_pin,),
                    "net": (sda_net,),
                },
            )
        )
    return tuple(findings)
