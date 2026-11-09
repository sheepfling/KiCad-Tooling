"""Reachability probe for the reviewed heterogeneous power-input rule."""

from __future__ import annotations

from tests.design_lint_fixtures.connector_reviewed_peer_power_input import (
    lint_report,
    power_input_coverage,
    power_input_netlist,
)


def reviewed_peer_power_input_rule_ids() -> set[str]:
    """Return findings emitted by the synthetic complete peer-power fixture."""
    observed = power_input_netlist()
    coverage = power_input_coverage(observed)
    return {item.rule_id for item in lint_report(observed, coverage).findings}
