"""Review a USB-C connector whose CC1 and CC2 pins share one net."""

from __future__ import annotations

from .bus_signal_roles import usb_c_cc_role
from .connector_identity import connector_candidate_references
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

RULE_ID: DesignLintRuleId = "bus.usb_c_cc_same_net"


def usb_c_cc_same_net_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Review one fitted connector with unique CC1 and CC2 pins on one exact net.

    Native pin functions, connector discovery, pin inventory, and unambiguous
    net assignments are recognition evidence. They do not establish the port's
    role or whether a shared assignment is valid for its exact design.
    """
    components = {reference.casefold(): reference for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, reviewed_connector_references)
    }
    inventory_by_reference = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    assignments_by_pin = netlist_pin_net_index(observed)
    cc_pins_by_reference: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        role = usb_c_cc_role(function)
        if not separator or not number or role is None:
            continue
        cc_pins_by_reference.setdefault(reference.casefold(), {}).setdefault(role, []).append(
            (pin, function)
        )

    findings: list[Candidate] = []
    for reference_key, roles in sorted(cc_pins_by_reference.items()):
        reference = components.get(reference_key)
        if (
            reference is None
            or reference_key not in connector_references
            or reference_key in dnp
            or len(roles.get("CC1", ())) != 1
            or len(roles.get("CC2", ())) != 1
        ):
            continue

        inventory = inventory_by_reference.get(reference_key)
        if inventory is None:
            continue
        cc1_pin, cc1_function = roles["CC1"][0]
        cc2_pin, cc2_function = roles["CC2"][0]
        if any(pin.rpartition(".")[2].casefold() not in inventory for pin in (cc1_pin, cc2_pin)):
            continue

        cc1_assignments = assignments_by_pin.get(cc1_pin.casefold(), set())
        cc2_assignments = assignments_by_pin.get(cc2_pin.casefold(), set())
        if len(cc1_assignments) != 1 or len(cc2_assignments) != 1:
            continue
        cc1_net, cc2_net = next(iter(cc1_assignments)), next(iter(cc2_assignments))
        if cc1_net != cc2_net:
            continue

        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: USB-C CC1/CC2 pins share {cc1_net}",
                message=(
                    f"The fitted USB-C connector {reference} has CC1 pin {cc1_pin} "
                    f"({cc1_function}) and CC2 pin {cc2_pin} ({cc2_function}) on one "
                    f"schematic net ({cc1_net}). Review the intended port-role map and "
                    "connection. Pin names are recognition clues; this review does not "
                    "establish the exact connector behavior, USB-C compliance, PCB copper, "
                    "or physical continuity."
                ),
                evidence={
                    "connector": (reference,),
                    "CC1_pin": (cc1_pin,),
                    "CC1_function": (cc1_function,),
                    "CC2_pin": (cc2_pin,),
                    "CC2_function": (cc2_function,),
                    "net": (cc1_net,),
                },
            )
        )
    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
