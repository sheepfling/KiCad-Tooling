"""Reachability probe for the reviewed heterogeneous power-input rule."""

from __future__ import annotations

from tests.design_lint_fixtures.connector_reviewed_peer_power_input import (
    lint_report,
    power_input_coverage,
    power_input_netlist,
)


def reviewed_peer_power_input_rule_ids() -> set[str]:
    """Return findings emitted by the synthetic split and passive-open cases."""
    observed = power_input_netlist()
    coverage = power_input_coverage(observed)
    split_rule_ids = {item.rule_id for item in lint_report(observed, coverage).findings}
    passive_open = power_input_netlist(
        electrical_type="passive",
        power_assignments=("USB_5V", None),
    )
    passive_open_report = lint_report(passive_open, power_input_coverage(passive_open))
    return split_rule_ids | {item.rule_id for item in passive_open_report.findings}
