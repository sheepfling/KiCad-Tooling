"""Reachability probe for shared peer signals with distinct mapped domains."""

from __future__ import annotations

from tests.design_lint_fixtures.connector_reviewed_peer_signal_split import (
    peer_signal_coverage,
    peer_signal_netlist,
    peer_signal_report,
)


def reviewed_peer_signal_domain_rule_ids() -> set[str]:
    """Return rules emitted when reviewed generic peers share a signal net."""
    observed = peer_signal_netlist(nets=("SHARED_RX", "SHARED_RX"))
    coverage = peer_signal_coverage(
        observed,
        voltage_domains=("logic-3v3", "logic-5v"),
    )
    return {item.rule_id for item in peer_signal_report(observed, coverage=coverage).findings}
