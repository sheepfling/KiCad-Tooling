"""Reachability probes for the reviewed connector peer power rules."""

from __future__ import annotations

from tests.design_lint_fixtures.connector_reviewed_peer_power_input import (
    lint_report,
    power_input_coverage,
    power_input_netlist,
)


def reviewed_peer_power_rule_ids() -> set[str]:
    """Return findings emitted by synthetic peer input and output cases."""
    observed = power_input_netlist()
    coverage = power_input_coverage(observed)
    split_rule_ids = {item.rule_id for item in lint_report(observed, coverage).findings}
    passive_open = power_input_netlist(
        electrical_type="passive",
        power_assignments=("USB_5V", None),
    )
    passive_open_report = lint_report(passive_open, power_input_coverage(passive_open))
    output_cases = (
        power_input_netlist(
            functions=("VBUS", "VDD_OUT"),
            electrical_type="power_out",
        ),
        power_input_netlist(
            functions=("VBUS", "VDD_OUT"),
            electrical_type="power_out",
            power_assignments=(None, "SERIAL_5V"),
        ),
    )
    output_rule_ids = {
        item.rule_id
        for observed_output in output_cases
        for item in lint_report(
            observed_output,
            power_input_coverage(
                observed_output,
                interface_signals=("POWER_OUTPUT", "POWER_OUTPUT"),
                roles=("supply", "supply"),
                directions=("output", "output"),
            ),
        ).findings
    }
    return (
        split_rule_ids | {item.rule_id for item in passive_open_report.findings} | output_rule_ids
    )
