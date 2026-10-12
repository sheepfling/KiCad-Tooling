"""Verify source-bound generic component power-input lint fixtures."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

GENERIC_COMPONENT_POWER_INPUT_CASES = (
    "unconnected-generic-component-power-input-fault",
    "unconnected-generic-component-power-input-no-connect-fault",
    "unconnected-generic-component-power-input-control",
    "unconnected-generic-component-power-input-dnp-control",
)


def verify_generic_component_power_input_cases(ctx: ConnectorReturnFixtureContext) -> None:
    """Check native evidence for missing, no-connect, assigned, and DNP pins."""
    if not set(GENERIC_COMPONENT_POWER_INPUT_CASES) <= set(ctx.cases):
        raise ValueError("Generic component power-input fixture set is incomplete")

    fault_cases = (
        "unconnected-generic-component-power-input-fault",
        "unconnected-generic-component-power-input-no-connect-fault",
    )
    expected_subject = "U1.1: generic native power-input pin is unassigned"
    for case in fault_cases:
        report = ctx.reports[case, "first"]
        if (
            report.status != "REVIEW"
            or {finding.rule_id for finding in report.findings}
            != {"component.unconnected_power_input"}
            or {finding.subject for finding in report.findings} != {expected_subject}
        ):
            raise ValueError(f"{case} lost its exact native power-input review finding")

    for case in (
        "unconnected-generic-component-power-input-control",
        "unconnected-generic-component-power-input-dnp-control",
    ):
        report = ctx.reports[case, "first"]
        if report.status != "PASS" or report.findings:
            raise ValueError(f"{case} no longer passes without lint findings")

    if (
        ctx.observed_contracts[
            "unconnected-generic-component-power-input-fault", "first"
        ].pin_electrical_types
        != {"U1.1": "power_in", "U1.2": "passive"}
        or ctx.observed_contracts[
            "unconnected-generic-component-power-input-control", "first"
        ].nets.get("POWER_INPUT_TEST")
        != ("U1.1",)
        or "U1"
        not in ctx.observed_contracts[
            "unconnected-generic-component-power-input-dnp-control", "first"
        ].dnp_components
    ):
        raise ValueError("Generic component power-input fixture lost native pin evidence")
