"""Review asymmetric direct assignments on fitted USB-C SBU function pairs."""

from __future__ import annotations

from dataclasses import dataclass

from .bus_signal_roles import usb_c_sbu_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index


@dataclass(frozen=True, slots=True)
class UnconnectedUsbCSbuPin:
    pin: str
    function: str
    paired_pin: str
    paired_function: str
    paired_net: str


RULE_ID: DesignLintRuleId = "bus.usb_c_sbu_unconnected_pin"


def unconnected_usb_c_sbu_pins(
    observed: NetlistContract,
) -> tuple[UnconnectedUsbCSbuPin, ...]:
    """Find one open SBU pin beside its uniquely assigned SBU peer on a fitted IC.

    Native pin functions are only a review clue. A fully open pair, duplicate
    roles, incomplete inventory, DNP part, or ambiguous net assignment is
    omitted because those cases do not establish an active partial path.
    """
    component_references = {reference.casefold() for reference in observed.components}
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    component_pin_numbers = {
        reference.casefold(): {str(number).casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    assignments = netlist_pin_net_index(observed)
    roles: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        if (
            not separator
            or not reference_key.startswith(("u", "ic"))
            or reference_key not in component_references
            or reference_key in dnp_references
            or number.casefold() not in component_pin_numbers.get(reference_key, set())
        ):
            continue
        role = usb_c_sbu_role(function)
        if role is not None:
            roles.setdefault(reference_key, {}).setdefault(role, []).append((pin, function))

    found: list[UnconnectedUsbCSbuPin] = []
    for component_roles in roles.values():
        sbu1, sbu2 = component_roles.get("SBU1", []), component_roles.get("SBU2", [])
        if len(sbu1) != 1 or len(sbu2) != 1:
            continue
        (sbu1_pin, sbu1_function), (sbu2_pin, sbu2_function) = sbu1[0], sbu2[0]
        sbu1_nets = assignments.get(sbu1_pin.casefold(), set())
        sbu2_nets = assignments.get(sbu2_pin.casefold(), set())
        if not sbu1_nets and len(sbu2_nets) == 1:
            found.append(
                UnconnectedUsbCSbuPin(
                    pin=sbu1_pin,
                    function=sbu1_function,
                    paired_pin=sbu2_pin,
                    paired_function=sbu2_function,
                    paired_net=next(iter(sbu2_nets)),
                )
            )
        elif not sbu2_nets and len(sbu1_nets) == 1:
            found.append(
                UnconnectedUsbCSbuPin(
                    pin=sbu2_pin,
                    function=sbu2_function,
                    paired_pin=sbu1_pin,
                    paired_function=sbu1_function,
                    paired_net=next(iter(sbu1_nets)),
                )
            )
    return tuple(sorted(found, key=lambda item: (item.pin.casefold(), item.function.casefold())))


def usb_c_sbu_unconnected_pin_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Build localized review prompts for asymmetric SBU assignments."""
    return tuple(
        Candidate(
            rule_id=RULE_ID,
            subject=f"{item.pin}: {item.function}",
            message=(
                f"This fitted IC {item.function} pin is unassigned while its paired "
                f"{item.paired_function} pin {item.paired_pin} is assigned to "
                f"{item.paired_net}. Review whether this partial SBU path is intentional "
                "or a connection is missing. Function names do not establish controller "
                "identity, alternate-mode use, or PCB routing."
            ),
            evidence={
                item.pin: (),
                "function": (item.function,),
                "usb_c_sbu_role": (item.function,),
                "paired_pin": (item.paired_pin,),
                "paired_function": (item.paired_function,),
                "paired_net": (item.paired_net,),
            },
        )
        for item in unconnected_usb_c_sbu_pins(observed)
    )
