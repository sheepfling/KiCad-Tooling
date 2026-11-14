"""Review fitted resistors directly bridging USB 2.0 D+/D- nets."""

from __future__ import annotations

from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .resistor_paths import direct_resistors
from .usb_data_pair_endpoints import usb_data_pair_endpoints

RULE_ID = "bus.usb_dp_dm_resistive_bridge"


def usb_data_pair_resistive_bridge_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Prompt review when a fitted two-terminal resistor bridges a USB-like pair.

    A resistor may intentionally terminate or bias a pair, so this heuristic
    does not assert a fault or required topology.
    """
    resistors = direct_resistors(
        observed,
        include_zero_ohm=True,
        include_device_r_symbol=True,
    )
    findings: list[Candidate] = []
    for endpoint in usb_data_pair_endpoints(observed):
        if endpoint.positive_net.casefold() == endpoint.negative_net.casefold():
            continue
        pair_nets = {endpoint.positive_net.casefold(), endpoint.negative_net.casefold()}
        port_label = "unindexed" if endpoint.port_group is None else endpoint.port_group
        for resistor in resistors:
            if {resistor.first_net.casefold(), resistor.second_net.casefold()} != pair_nets:
                continue
            value = f"{resistor.resistance_ohms:g}Ω"
            findings.append(
                Candidate(
                    rule_id=RULE_ID,
                    subject=(
                        f"{endpoint.reference}: USB data port {port_label} D+/D- nets "
                        f"{endpoint.positive_net} and {endpoint.negative_net} are bridged "
                        f"by {resistor.reference}"
                    ),
                    message=(
                        f"A fitted two-terminal resistor {resistor.reference} ({value}) "
                        f"directly bridges the schematic nets assigned to D+ "
                        f"({endpoint.positive_pin}) and D- ({endpoint.negative_pin}) on "
                        f"{endpoint.reference}. Review whether this is intentional; a "
                        "differential termination or other designed shunt may be valid. "
                        "Function names do not prove USB use, required topology, PCB copper, "
                        "or off-board connectivity."
                    ),
                    evidence={
                        "component": (endpoint.reference,),
                        "USB_port_group": (port_label,),
                        "D+_pin": (endpoint.positive_pin,),
                        "D-_pin": (endpoint.negative_pin,),
                        "D+_net": (endpoint.positive_net,),
                        "D-_net": (endpoint.negative_net,),
                        "resistor": (resistor.reference,),
                        "resistance_ohms": (value,),
                    },
                )
            )
    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
