"""Review fitted USB 2.0 PHY data pins assigned to one net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .usb_data_pair_endpoints import usb_data_pair_endpoints

RULE_ID = "bus.usb_dp_dm_same_net"


def usb_data_same_net_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find an explicit USB 2.0 D+/D- pair assigned to the same exact net."""
    findings: list[Candidate] = []
    for endpoint in usb_data_pair_endpoints(observed):
        if endpoint.positive_net.casefold() != endpoint.negative_net.casefold():
            continue
        if endpoint.positive_net != endpoint.negative_net:
            continue
        if endpoint.positive_type == endpoint.negative_type == "output":
            continue
        port_label = "unindexed" if endpoint.port_group is None else endpoint.port_group
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{endpoint.reference}: USB data port {port_label} D+/D- pins "
                    f"share {endpoint.positive_net}"
                ),
                message=(
                    f"The explicit USB 2.0 D+ pin {endpoint.positive_pin} and D- pin "
                    f"{endpoint.negative_pin} on {endpoint.reference} share one schematic "
                    f"net ({endpoint.positive_net}). Review whether this is intentional. "
                    "Function names are clues only; this check does not prove the part "
                    "implements USB or establish the intended topology."
                ),
                evidence={
                    "component": (endpoint.reference,),
                    "USB_port_group": (port_label,),
                    "D+_pin": (endpoint.positive_pin,),
                    "D-_pin": (endpoint.negative_pin,),
                    "D+_electrical_type": (endpoint.positive_type,),
                    "D-_electrical_type": (endpoint.negative_type,),
                    "net": (endpoint.positive_net,),
                },
            )
        )
    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
