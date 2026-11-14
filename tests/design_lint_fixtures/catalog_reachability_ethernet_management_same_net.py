"""Synthetic catalog coverage for Ethernet MDC/MDIO same-net review."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import candidates
from tests.design_lint_fixtures.ethernet_management_same_net import (
    ethernet_management_same_net_netlist,
)


def ethernet_management_same_net_rule_ids() -> set[str]:
    """Return the lint rule IDs emitted by the complete same-net fault case."""
    return {item.rule_id for item in candidates(ethernet_management_same_net_netlist())}
