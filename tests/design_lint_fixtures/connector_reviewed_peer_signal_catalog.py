"""Reachability probe for reviewed peer signal assignments."""

from __future__ import annotations

from tests.design_lint_fixtures.connector_reviewed_peer_signal_split import (
    peer_signal_netlist,
    peer_signal_report,
)


def reviewed_peer_signal_assignment_rule_ids() -> set[str]:
    """Return findings emitted by the synthetic split signal peers."""
    observed = peer_signal_netlist()
    return {item.rule_id for item in peer_signal_report(observed).findings}
