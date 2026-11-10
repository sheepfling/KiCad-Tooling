"""Synthetic reachability for mapped connector role-pair reviews."""

from __future__ import annotations

from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
    signal_sharing_coverage,
    signal_sharing_netlist,
    signal_sharing_report,
)
from tests.design_lint_fixtures.connector_mapped_supply_return_net import (
    mapped_supply_return_net_netlist,
    mapped_supply_return_net_report,
)


def mapped_contact_sharing_rule_ids() -> set[str]:
    """Reach mapped supply/return and supply/shield shared-net rules."""
    return_report, _ = mapped_supply_return_net_report(mapped_supply_return_net_netlist())
    source = signal_sharing_netlist()
    coverage = signal_sharing_coverage(
        source,
        signal_names=("SUPPLY_CONTACT", "CABLE_SHIELD"),
        roles=("supply", "shield"),
    )
    shield_report, _ = signal_sharing_report(source, coverage=coverage)
    return {item.rule_id for item in (*return_report.findings, *shield_report.findings)}
