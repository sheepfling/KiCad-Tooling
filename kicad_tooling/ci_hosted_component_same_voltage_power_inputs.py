"""Verify native same-voltage split supply-input fixtures."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

SAME_VOLTAGE_POWER_INPUT_CASES = (
    "same-voltage-power-input-split-fault",
    "same-voltage-power-input-common-control",
)
RULE_ID = "component.same_voltage_power_inputs_split"


def verify_same_voltage_power_input_cases(ctx: ConnectorReturnFixtureContext) -> None:
    """Check source-bound fault/control pin identities and the configured review."""
    if set(ctx.cases) != set(SAME_VOLTAGE_POWER_INPUT_CASES):
        raise ValueError("Same-voltage power-input fixture set is incomplete")

    fault_case, control_case = SAME_VOLTAGE_POWER_INPUT_CASES
    fault = ctx.reports[fault_case, "first"]
    observed_fault = ctx.observed_contracts[fault_case, "first"]
    findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
    if (
        fault.status != "REVIEW"
        or len(findings) != 1
        or findings[0].evidence != {"U1.1": ("+3V3",), "U1.2": ("3.3V",)}
        or observed_fault.pin_functions != {"U1.1": "VDD", "U1.2": "VDDIO"}
        or observed_fault.pin_electrical_types != {"U1.1": "power_in", "U1.2": "power_in"}
        or observed_fault.component_pin_numbers != {"U1": ("1", "2")}
    ):
        raise ValueError("Native same-voltage power-input fault lost its expected evidence")

    control = ctx.reports[control_case, "first"]
    observed_control = ctx.observed_contracts[control_case, "first"]
    if (
        any(item.rule_id == RULE_ID for item in control.findings)
        or observed_control.nets.get("+3V3") != ("U1.1", "U1.2")
        or observed_control.pin_functions != {"U1.1": "VDD", "U1.2": "VDDIO"}
        or observed_control.pin_electrical_types != {"U1.1": "power_in", "U1.2": "power_in"}
    ):
        raise ValueError("Native common-rail control no longer clears the target rule")
