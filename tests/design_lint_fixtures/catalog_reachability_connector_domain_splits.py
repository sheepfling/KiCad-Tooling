"""Minimal catalog reachability inputs for mapped connector domain splits."""

from __future__ import annotations

from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
    signal_sharing_coverage,
    signal_sharing_netlist,
    signal_sharing_report,
)


def mapped_connector_domain_split_rule_ids() -> set[str]:
    """Return rules reached by same-domain supply and return pins on split nets."""
    supply_source = signal_sharing_netlist(
        first_net="SUPPLY_SEGMENT_A",
        second_net="SUPPLY_SEGMENT_B",
    )
    supply_coverage = signal_sharing_coverage(
        supply_source,
        signal_names=("SUPPLY_CONTACT_A", "SUPPLY_CONTACT_B"),
        roles=("supply", "supply"),
    )
    return_source = signal_sharing_netlist(
        first_net="RETURN_SEGMENT_A",
        second_net="RETURN_SEGMENT_B",
    )
    return_coverage = signal_sharing_coverage(
        return_source,
        signal_names=("RETURN_CONTACT_A", "RETURN_CONTACT_B"),
        roles=("return", "return"),
        voltage_domains=("signal-return", "signal-return"),
    )
    reports = (
        signal_sharing_report(supply_source, coverage=supply_coverage)[0],
        signal_sharing_report(return_source, coverage=return_coverage)[0],
    )
    return {item.rule_id for report in reports for item in report.findings}
