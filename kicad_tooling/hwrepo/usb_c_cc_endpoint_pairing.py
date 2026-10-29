"""Review crossed USB-C CC nets between a connector and controller."""

from __future__ import annotations

import re

from .bus_signal_roles import usb_c_cc_role
from .connector_identity import connector_candidate_references
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

RULE_ID: DesignLintRuleId = "bus.usb_c_cc_endpoint_crossed"
_CONTROLLER_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


def crossed_usb_c_cc_endpoint_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review a unique connector/controller CC pair assigned to opposite nets.

    Both endpoints need unique native CC1/CC2 functions, complete pin
    inventories, fitted state, and direct unambiguous assignments. Ambiguous
    endpoint groups and same-net pairs are left to other checks.
    """
    components = {reference.casefold(): reference for reference in observed.components}
    connectors = {reference.casefold() for reference in connector_candidate_references(observed)}
    controllers = {
        reference.casefold()
        for reference in observed.components
        if _CONTROLLER_REFERENCE.fullmatch(reference)
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventory = {
        reference.casefold(): {str(number).casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    assignments = netlist_pin_net_index(observed)
    roles: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        key = reference.casefold()
        role = usb_c_cc_role(function)
        if not separator or not number or role is None or key not in components:
            continue
        roles.setdefault(key, {}).setdefault(role, []).append((pin, function))

    endpoint_groups: dict[tuple[str, str], dict[str, list[tuple[str, str, str]]]] = {}
    for key, endpoint_roles in roles.items():
        if key in dnp or (key not in connectors and key not in controllers):
            continue
        cc1, cc2 = endpoint_roles.get("CC1", ()), endpoint_roles.get("CC2", ())
        if len(cc1) != 1 or len(cc2) != 1:
            continue
        cc1_pin, _ = cc1[0]
        cc2_pin, _ = cc2[0]
        complete_inventory = inventory.get(key)
        if complete_inventory is None or any(
            pin.rpartition(".")[2].casefold() not in complete_inventory
            for pin in (cc1_pin, cc2_pin)
        ):
            continue
        cc1_nets = assignments.get(cc1_pin.casefold(), set())
        cc2_nets = assignments.get(cc2_pin.casefold(), set())
        if len(cc1_nets) != 1 or len(cc2_nets) != 1:
            continue
        cc1_net, cc2_net = next(iter(cc1_nets)), next(iter(cc2_nets))
        if cc1_net == cc2_net:
            continue
        ordered_nets = sorted((cc1_net, cc2_net), key=lambda net: (net.casefold(), net))
        pair: tuple[str, str] = (ordered_nets[0], ordered_nets[1])
        endpoint_type = "connector" if key in connectors else "controller"
        endpoint_groups.setdefault(pair, {}).setdefault(endpoint_type, []).append(
            (components[key], cc1_net, cc2_net)
        )

    findings: list[Candidate] = []
    for net_pair, endpoints in sorted(endpoint_groups.items()):
        connector_endpoints = endpoints.get("connector", ())
        controller_endpoints = endpoints.get("controller", ())
        if len(connector_endpoints) != 1 or len(controller_endpoints) != 1:
            continue
        connector, connector_cc1_net, connector_cc2_net = connector_endpoints[0]
        controller, controller_cc1_net, controller_cc2_net = controller_endpoints[0]
        if (connector_cc1_net, connector_cc2_net) != (controller_cc2_net, controller_cc1_net):
            continue
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{connector}/{controller}: USB-C CC1/CC2 endpoint nets appear crossed",
                message=(
                    f"Recognized USB-C connector {connector} assigns CC1 to {connector_cc1_net} "
                    f"and CC2 to {connector_cc2_net}, while controller {controller} assigns "
                    f"CC1 to {controller_cc1_net} and CC2 to {controller_cc2_net}. Review the "
                    "exact controller pinout and port map. This is a schematic-topology clue, "
                    "not proof that the mapping is wrong or that PCB copper is correct."
                ),
                evidence={
                    "connector": (connector,),
                    "controller": (controller,),
                    "connector_CC1_net": (connector_cc1_net,),
                    "connector_CC2_net": (connector_cc2_net,),
                    "controller_CC1_net": (controller_cc1_net,),
                    "controller_CC2_net": (controller_cc2_net,),
                    "nets": net_pair,
                },
            )
        )
    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
