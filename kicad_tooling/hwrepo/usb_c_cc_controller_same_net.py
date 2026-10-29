"""Review USB-C controller CC1/CC2 pins assigned to one schematic net."""

from __future__ import annotations

import re

from .bus_signal_roles import usb_c_cc_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

RULE_ID: DesignLintRuleId = "bus.usb_c_cc_controller_same_net"
_CONTROLLER_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


def usb_c_cc_controller_same_net_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review fitted U/IC components whose unique CC1 and CC2 pins share one net.

    Pin names and assignments identify a review candidate only. Incomplete,
    ambiguous, open, DNP, or native-output pairs are excluded.
    """
    fitted = {
        reference.casefold(): reference
        for reference in observed.components
        if _CONTROLLER_REFERENCE.fullmatch(reference)
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventory = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    assignments = netlist_pin_net_index(observed)
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    roles: dict[str, dict[str, list[tuple[str, str]]]] = {}
    invalid: set[str] = set()
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        key = reference.casefold()
        role = usb_c_cc_role(function)
        if not separator or key not in fitted or role is None:
            continue
        if number.casefold() not in inventory.get(key, set()):
            invalid.add(key)
            continue
        roles.setdefault(key, {}).setdefault(role, []).append((pin, function))

    findings: list[Candidate] = []
    for key, component_roles in sorted(roles.items()):
        if key in dnp or key in invalid:
            continue
        cc1, cc2 = component_roles.get("CC1", ()), component_roles.get("CC2", ())
        if len(cc1) != 1 or len(cc2) != 1:
            continue
        cc1_pin, cc1_function = cc1[0]
        cc2_pin, cc2_function = cc2[0]
        cc1_nets = assignments.get(cc1_pin.casefold(), set())
        cc2_nets = assignments.get(cc2_pin.casefold(), set())
        if len(cc1_nets) != 1 or len(cc2_nets) != 1 or cc1_nets != cc2_nets:
            continue
        if pin_types.get(cc1_pin.casefold()) == pin_types.get(cc2_pin.casefold()) == "output":
            continue
        reference = fitted[key]
        net = next(iter(cc1_nets))
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: USB-C controller CC1/CC2 pins share {net}",
                message=(
                    f"The fitted USB-C controller {reference} has CC1 pin {cc1_pin} "
                    f"({cc1_function}) and CC2 pin {cc2_pin} ({cc2_function}) assigned "
                    f"to one schematic net ({net}). Review the exact controller pinout "
                    "and port topology. This does not establish that the pins must be "
                    "separate, prove USB-C behavior, or assess PCB copper or continuity."
                ),
                evidence={
                    "component": (reference,),
                    "CC1_pin": (cc1_pin,),
                    "CC1_function": (cc1_function,),
                    "CC2_pin": (cc2_pin,),
                    "CC2_function": (cc2_function,),
                    "net": (net,),
                },
            )
        )
    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
