"""Review explicit I3C SDA/SCL pairs assigned to one schematic net."""

from __future__ import annotations

import re

from .bus_signal_roles import i3c_signal_identity
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "bus.i3c_sda_scl_same_net"
_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


def i3c_sda_scl_same_net_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find fitted ICs whose unique, complete I3C signal pair shares one net."""
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

    roles_by_reference: dict[
        str, dict[tuple[str | None, str], list[tuple[str, tuple[str, ...]]]]
    ] = {}
    invalid_inventory_references: set[str] = set()
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        if not separator or reference_key not in fitted:
            continue
        identity = i3c_signal_identity(function)
        if identity is None:
            continue
        inventory = pin_numbers.get(reference_key, set())
        if not inventory or number.casefold() not in inventory:
            invalid_inventory_references.add(reference_key)
            continue
        assignments = tuple(
            sorted(nets_by_pin.get(pin.casefold(), ()), key=lambda item: (item.casefold(), item))
        )
        roles_by_reference.setdefault(reference_key, {}).setdefault(
            (identity.channel, identity.role), []
        ).append((f"{fitted[reference_key]}.{number}", assignments))

    findings: list[Candidate] = []
    for reference_key, roles in sorted(roles_by_reference.items()):
        if reference_key in dnp or reference_key in invalid_inventory_references:
            continue
        channels = sorted(
            {channel for channel, _ in roles}, key=lambda item: (item is not None, item or "")
        )
        for channel in channels:
            sda_pins = roles.get((channel, "SDA"), ())
            scl_pins = roles.get((channel, "SCL"), ())
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
            channel_text = "unindexed" if channel is None else channel
            findings.append(
                Candidate(
                    rule_id=RULE_ID,
                    subject=f"{reference}: I3C{channel_text} SDA/SCL pins share {sda_net}",
                    message=(
                        f"The explicit I3C SDA pin {sda_pin} and SCL pin {scl_pin} on "
                        f"{reference} share one schematic net ({sda_net}). Review whether "
                        "this is intentional. Function names are clues only; this check does "
                        "not prove the part implements I3C or establish its intended topology."
                    ),
                    evidence={
                        "component": (reference,),
                        "channel": (channel_text,),
                        "SDA_pin": (sda_pin,),
                        "SCL_pin": (scl_pin,),
                        "net": (sda_net,),
                    },
                )
            )
    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
