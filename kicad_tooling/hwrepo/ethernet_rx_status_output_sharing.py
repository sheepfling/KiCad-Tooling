"""Review shared Ethernet PHY receive-status outputs."""

from __future__ import annotations

import re

from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .ethernet_phy_identity import explicit_ethernet_phy_identity
from .netlist_contract_models import NetlistContract
from .signal_pair_output_sharing import signal_output_sharing_groups

RULE_ID = "bus.ethernet_rx_status_outputs_share_net"
_RX_STATUS_FUNCTION = re.compile(r"(?:(?:gmii|mii))?(rxdv|rxer)")


def ethernet_phy_rx_status_output_role(_reference: str, function: str) -> tuple[str, str] | None:
    """Recognize bounded MII/GMII RXDV and RXER function aliases."""
    normalized = re.sub(r"[^a-z0-9]", "", function.casefold())
    match = _RX_STATUS_FUNCTION.fullmatch(normalized)
    if match is None:
        return None
    signal = match.group(1)
    return "rx", f"ethernet-mii-receive-status-{signal}"


def ethernet_rx_status_output_sharing_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review fitted, identified PHY receive-status pins sharing one net."""

    def role_and_channel(reference: str, function: str) -> tuple[str, str] | None:
        if explicit_ethernet_phy_identity(observed, reference) is None:
            return None
        return ethernet_phy_rx_status_output_role(reference, function)

    groups = signal_output_sharing_groups(
        observed,
        role_and_channel=role_and_channel,
        expected_role="rx",
        is_supported_reference=is_integrated_circuit_reference,
        require_pin_inventory=True,
        skip_return_like_nets=True,
        exclude_nets_with_incomplete_evidence=True,
    )
    findings: list[Candidate] = []
    for group in groups:
        if len(set(group.channels)) != 1:
            continue
        identity_basis = tuple(
            sorted(
                {
                    explicit_ethernet_phy_identity(observed, reference) or ""
                    for reference in group.components
                },
                key=str.casefold,
            )
        )
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{', '.join(group.components)}: Ethernet PHY receive-status outputs "
                    f"share {group.net}"
                ),
                message=(
                    f"Fitted Ethernet PHY receive-status pins {', '.join(group.pins)} "
                    f"({', '.join(group.functions)}) share one schematic net ({group.net}) "
                    f"with native pin types {', '.join(group.pin_types)}. Review whether "
                    "the status outputs are intentionally combined for the selected PHY mode. "
                    "The heuristic does not infer mode, endpoint selection, board copper, or "
                    "off-board wiring."
                ),
                evidence={
                    "components": group.components,
                    "channels": group.channels,
                    "functions": group.functions,
                    "pins": group.pins,
                    "pin_types": group.pin_types,
                    "net": (group.net,),
                    "identity_basis": identity_basis,
                },
            )
        )
    return tuple(findings)
