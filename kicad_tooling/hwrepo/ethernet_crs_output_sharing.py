"""Review shared Ethernet PHY MII carrier-sense outputs."""

from __future__ import annotations

import re

from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .ethernet_phy_identity import explicit_ethernet_phy_identity
from .netlist_contract_models import NetlistContract
from .signal_pair_output_sharing import signal_output_sharing_groups

RULE_ID = "bus.ethernet_crs_outputs_share_net"
_CRS_FUNCTION = re.compile(r"(?:mii)?crs")


def ethernet_phy_crs_output_role(_reference: str, function: str) -> tuple[str, str] | None:
    """Recognize exact CRS and MII_CRS function labels."""
    normalized = re.sub(r"[^a-z0-9]", "", function.casefold())
    if _CRS_FUNCTION.fullmatch(normalized) is None:
        return None
    return "rx", "ethernet-mii-carrier-sense"


def ethernet_crs_output_sharing_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review fitted, identified PHYs with one shared MII CRS output net."""

    def role_and_channel(reference: str, function: str) -> tuple[str, str] | None:
        if explicit_ethernet_phy_identity(observed, reference) is None:
            return None
        return ethernet_phy_crs_output_role(reference, function)

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
                    f"{', '.join(group.components)}: Ethernet PHY CRS outputs share {group.net}"
                ),
                message=(
                    f"Fitted Ethernet PHY carrier-sense pins {', '.join(group.pins)} "
                    f"share one schematic net ({group.net}) with native pin types "
                    f"{', '.join(group.pin_types)}. Review whether the selected PHY mode "
                    "and endpoint selection make this connection intentional. Pin names "
                    "do not prove MII mode, active output behavior, board copper, or "
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
