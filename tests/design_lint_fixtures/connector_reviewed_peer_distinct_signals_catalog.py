"""Reachability probe for distinct peer signal names sharing one net."""

from __future__ import annotations

from tests.design_lint_fixtures.connector_reviewed_peer_signal_split import (
    peer_signal_coverage,
    peer_signal_netlist,
    peer_signal_report,
)


def reviewed_peer_distinct_signal_rule_ids() -> set[str]:
    """Return rules emitted by complete reviewed peers with distinct shared-net signals."""
    observed = peer_signal_netlist(nets=("SHARED_SIGNAL", "SHARED_SIGNAL"))
    coverage = peer_signal_coverage(observed, signals=("UART_TX", "UART_RX"))
    return {item.rule_id for item in peer_signal_report(observed, coverage=coverage).findings}
