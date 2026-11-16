"""Review multiple fitted Ethernet PHY receive-data outputs on one net."""

from __future__ import annotations

import re

from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .ethernet_phy_identity import explicit_ethernet_phy_identity
from .netlist_contract_models import NetlistContract
from .signal_pair_output_sharing import signal_output_sharing_groups

RULE_ID = "bus.ethernet_rx_outputs_share_net"

_RX_DATA_FUNCTION = re.compile(r"(?:(?:rgmii|gmii|rmii|mii))?(?:rxd|rxdata)([0-7])?")


def ethernet_phy_rx_output_role(_reference: str, function: str) -> tuple[str, str] | None:
    """Recognize bounded MII-family RXD/RXDATA bit functions."""
    normalized = re.sub(r"[^a-z0-9]", "", function.casefold())
    match = _RX_DATA_FUNCTION.fullmatch(normalized)
    if match is None:
        return None
    bit = match.group(1)
    return "rx", f"ethernet-rx-data-{bit or 'unindexed'}"


def ethernet_rx_output_sharing_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Find supported fitted Ethernet PHY receive-data outputs sharing a net."""

    def role_and_channel(reference: str, function: str) -> tuple[str, str] | None:
        if explicit_ethernet_phy_identity(observed, reference) is None:
            return None
        return ethernet_phy_rx_output_role(reference, function)

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
                    f"{', '.join(group.components)}: Ethernet PHY receive-data outputs "
                    f"share {group.net}"
                ),
                message=(
                    f"Fitted Ethernet PHY receive-data pins {', '.join(group.pins)} share one "
                    f"schematic net ({group.net}) with native pin types "
                    f"{', '.join(group.pin_types)}. Review whether these outputs are "
                    "intentionally connected. A muxed or otherwise selected path may be valid; "
                    "component identity text, pin functions, and net assignments do not prove "
                    "output behavior, interface topology, PCB copper, or off-board wiring."
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
