"""Review USB-C SBU controller pins assigned to one schematic net."""

from __future__ import annotations

import re

from .bus_signal_roles import usb_c_sbu_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

RULE_ID: DesignLintRuleId = "bus.usb_c_sbu_same_net"
_CONTROLLER_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


def usb_c_sbu_same_net_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review one fitted controller with unique, assigned SBU1/SBU2 pins on one net.

    Function names and net assignments identify candidates only. The check
    excludes incomplete or ambiguous evidence and does not assert that the
    SBU lines must remain separate for a particular design.
    """
    fitted = {
        reference.casefold(): reference
        for reference in observed.components
        if _CONTROLLER_REFERENCE.fullmatch(reference)
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_numbers = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    assignments = netlist_pin_net_index(observed)
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    roles: dict[str, dict[str, list[tuple[str, str]]]] = {}
    invalid_inventory: set[str] = set()
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        role = usb_c_sbu_role(function)
        if not separator or reference_key not in fitted or role is None:
            continue
        if number.casefold() not in pin_numbers.get(reference_key, set()):
            invalid_inventory.add(reference_key)
            continue
        roles.setdefault(reference_key, {}).setdefault(role, []).append((pin, function))

    findings: list[Candidate] = []
    for reference_key, component_roles in sorted(roles.items()):
        if reference_key in dnp or reference_key in invalid_inventory:
            continue
        sbu1 = component_roles.get("SBU1", ())
        sbu2 = component_roles.get("SBU2", ())
        if len(sbu1) != 1 or len(sbu2) != 1:
            continue
        sbu1_pin, sbu1_function = sbu1[0]
        sbu2_pin, sbu2_function = sbu2[0]
        sbu1_nets = assignments.get(sbu1_pin.casefold(), set())
        sbu2_nets = assignments.get(sbu2_pin.casefold(), set())
        if len(sbu1_nets) != 1 or len(sbu2_nets) != 1:
            continue
        sbu1_net, sbu2_net = next(iter(sbu1_nets)), next(iter(sbu2_nets))
        if sbu1_net != sbu2_net:
            continue
        if pin_types.get(sbu1_pin.casefold()) == pin_types.get(sbu2_pin.casefold()) == "output":
            continue

        reference = fitted[reference_key]
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: USB-C SBU1/SBU2 pins share {sbu1_net}",
                message=(
                    f"The fitted USB-C controller {reference} has SBU1 pin {sbu1_pin} "
                    f"({sbu1_function}) and SBU2 pin {sbu2_pin} ({sbu2_function}) "
                    f"assigned to one schematic net ({sbu1_net}). Review the exact "
                    "controller pinout and intended port map. This does not establish "
                    "that the lines must be separate, prove USB-C behavior, or assess "
                    "PCB copper or physical continuity."
                ),
                evidence={
                    "component": (reference,),
                    "SBU1_pin": (sbu1_pin,),
                    "SBU1_function": (sbu1_function,),
                    "SBU2_pin": (sbu2_pin,),
                    "SBU2_function": (sbu2_function,),
                    "net": (sbu1_net,),
                },
            )
        )
    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
