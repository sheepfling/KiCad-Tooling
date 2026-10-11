"""Verify source-bound connector return-to-supply fault and control fixtures."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def verify_positive_rail_return_cases(ctx: ConnectorReturnFixtureContext) -> None:
    """Require the native fault to warn and its common-return control to stay clear."""
    fault_case = "return-positive-rail-fault"
    control_case = "return-positive-rail-control"
    fault = ctx.reports[fault_case, "first"]
    fault_source = ctx.observed_contracts[fault_case, "first"]
    control = ctx.reports[control_case, "first"]

    findings = {
        item.subject
        for item in fault.findings
        if item.rule_id == "connector.return_pin_on_positive_rail"
    }
    expected_subjects = {
        "J1.1: return assigned to +5V",
        "J1.2: return assigned to +5V",
    }
    expected_pins = ("J1.1", "J1.2")
    if (
        fault.status != "REVIEW"
        or findings != expected_subjects
        or set(fault_source.nets.get("+5V", ())) != {"J1.1", "J1.2"}
        or any(fault_source.pin_functions.get(pin) != "GND" for pin in expected_pins)
    ):
        raise ValueError(
            "Positive-rail return fault lost its exact native connector pin evidence: "
            f"status={fault.status}, findings={findings}, nets={fault_source.nets.get('+5V')!r}"
        )
    if control.status != "PASS" or any(
        item.rule_id == "connector.return_pin_on_positive_rail" for item in control.findings
    ):
        raise ValueError("Common-return control unexpectedly triggered the positive-rail lint")
