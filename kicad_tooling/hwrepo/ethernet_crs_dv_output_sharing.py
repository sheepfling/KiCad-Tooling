"""Review shared Ethernet PHY RMII CRS_DV outputs."""

from __future__ import annotations

import re

from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .ethernet_phy_identity import explicit_ethernet_phy_identity
from .netlist_contract_models import NetlistContract
from .signal_pair_output_sharing import signal_output_sharing_groups

RULE_ID = "bus.ethernet_crs_dv_outputs_share_net"
_CRS_DV_FUNCTION = re.compile(r"(?:rmii)?crsdv")


def ethernet_phy_crs_dv_output_role(_reference: str, function: str) -> tuple[str, str] | None:
    """Recognize bounded RMII CRS_DV and CRS-DV aliases."""
    normalized = re.sub(r"[^a-z0-9]", "", function.casefold())
    if _CRS_DV_FUNCTION.fullmatch(normalized) is None:
        return None
    return "rx", "ethernet-rmii-carrier-sense-rx-data-valid"


def ethernet_crs_dv_output_sharing_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review fitted, identified PHYs with one shared same-role CRS_DV net."""

    def role_and_channel(reference: str, function: str) -> tuple[str, str] | None:
        if explicit_ethernet_phy_identity(observed, reference) is None:
            return None
        return ethernet_phy_crs_dv_output_role(reference, function)

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
                    f"{', '.join(group.components)}: Ethernet PHY CRS_DV outputs share {group.net}"
                ),
                message=(
                    f"Fitted Ethernet PHY carrier-sense/receive-data-valid pins "
                    f"{', '.join(group.pins)} share one schematic net ({group.net}) with "
                    f"native pin types {', '.join(group.pin_types)}. Review whether multiple "
                    "PHY endpoints are intentionally combined for the selected topology. "
                    "Pin functions and net assignments do not prove RMII mode, endpoint "
                    "selection, board copper, or off-board wiring."
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
