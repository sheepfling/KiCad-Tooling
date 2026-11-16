"""Synthetic MII transmit-clock sharing netlists for lint regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.ethernet_output_sharing import (
    ethernet_phy_output_sharing_netlist,
)


def ethernet_mii_tx_clock_output_netlist(
    *,
    shared: bool = True,
    references: tuple[str, ...] = ("U1", "U2"),
    functions: tuple[str, ...] | None = None,
    net_name: str = "MII_TX_CLK_SHARED",
    pin_type: str = "passive",
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    """Build explicit Ethernet PHY identities with shared or separate TX_CLK pins."""
    return ethernet_phy_output_sharing_netlist(
        default_function="TX_CLK",
        pin_number="1",
        shared=shared,
        references=references,
        functions=functions,
        net_name=net_name,
        pin_type=pin_type,
        dnp_references=dnp_references,
    )
