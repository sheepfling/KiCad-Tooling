"""Minimal catalog reachability input for mapped supply-domain split review."""

from __future__ import annotations

from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
    signal_sharing_coverage,
    signal_sharing_netlist,
    signal_sharing_report,
)


def mapped_supply_domain_split_rule_ids() -> set[str]:
    """Return rules reached by two same-domain supplies on separate nets."""
    source = signal_sharing_netlist(
        first_net="SUPPLY_SEGMENT_A",
        second_net="SUPPLY_SEGMENT_B",
    )
    coverage = signal_sharing_coverage(
        source,
        signal_names=("SUPPLY_CONTACT_A", "SUPPLY_CONTACT_B"),
        roles=("supply", "supply"),
    )
    report, _ = signal_sharing_report(source, coverage=coverage)
    return {item.rule_id for item in report.findings}
