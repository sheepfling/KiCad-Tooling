"""Review shared Ethernet PHY MII receive-clock outputs."""

from __future__ import annotations

import re

from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .ethernet_phy_identity import explicit_ethernet_phy_identity
from .netlist_contract_models import NetlistContract
from .signal_pair_output_sharing import signal_output_sharing_groups

RULE_ID = "bus.ethernet_rx_clock_outputs_share_net"
_RX_CLOCK_FUNCTION = re.compile(r"(?:(?:rgmii|gmii|mii))?(?:rxc|rxclk)")


def ethernet_phy_rx_clock_output_role(_reference: str, function: str) -> tuple[str, str] | None:
    """Recognize bounded PHY receive-clock function aliases."""
    normalized = re.sub(r"[^a-z0-9]", "", function.casefold())
    if _RX_CLOCK_FUNCTION.fullmatch(normalized) is None:
        return None
    return "rx", "ethernet-mii-receive-clock"


def ethernet_rx_clock_output_sharing_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review fitted, identified PHY receive clocks assigned to one net."""

    def role_and_channel(reference: str, function: str) -> tuple[str, str] | None:
        if explicit_ethernet_phy_identity(observed, reference) is None:
            return None
        return ethernet_phy_rx_clock_output_role(reference, function)

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
                    f"{', '.join(group.components)}: Ethernet PHY receive-clock outputs "
                    f"share {group.net}"
                ),
                message=(
                    f"Fitted Ethernet PHY receive-clock pins {', '.join(group.pins)} share one "
                    f"schematic net ({group.net}) with native pin types "
                    f"{', '.join(group.pin_types)}. Review whether MII operation and endpoint "
                    "selection make this connection intentional. The heuristic does not infer "
                    "PHY mode, clock behavior, board copper, or off-board wiring."
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
