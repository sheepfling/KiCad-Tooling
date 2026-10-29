"""Catalog reachability for mapped connector role-sharing rules."""

from __future__ import annotations

from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
    signal_sharing_coverage,
    signal_sharing_netlist,
    signal_sharing_report,
)


def connector_role_sharing_rule_ids() -> set[str]:
    """Return mapped connector role-sharing findings from catalog cases."""
    emitted: set[str] = set()
    cases = (
        (signal_sharing_netlist(), ("CONTROL_A", "CONTROL_B"), ("signal", "signal")),
        (signal_sharing_netlist(), ("CABLE_SHIELD", "UART_RX"), ("shield", "signal")),
        (signal_sharing_netlist(), ("SIGNAL_RETURN", "UART_RX"), ("return", "signal")),
        (
            signal_sharing_netlist(first_net="CONTACT_NET_A", second_net="CONTACT_NET_B"),
            ("CONTROL_A", "control_a"),
            ("signal", "signal"),
        ),
    )
    for source, signal_names, roles in cases:
        coverage = signal_sharing_coverage(source, signal_names=signal_names, roles=roles)
        report, _coverage = signal_sharing_report(source, coverage=coverage)
        emitted.update(item.rule_id for item in report.findings)
    return emitted
