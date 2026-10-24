"""Verify exact native repeated signal-function pin fixtures."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext
from .hwrepo.design_lint_rule_types import DesignLintRuleId

COMPONENT_REPEATED_SIGNAL_PIN_FAULT = "repeated-signal-pin-fault"
COMPONENT_REPEATED_SIGNAL_PIN_CONTROL = "repeated-signal-pin-control"
COMPONENT_REPEATED_SIGNAL_PIN_CASES = (
    COMPONENT_REPEATED_SIGNAL_PIN_FAULT,
    COMPONENT_REPEATED_SIGNAL_PIN_CONTROL,
)
COMPONENT_REPEATED_SIGNAL_PIN_RULE_ID: DesignLintRuleId = (
    "component.repeated_signal_pin_assignment_divergence"
)


def verify_component_repeated_signal_pin_cases(ctx: ConnectorReturnFixtureContext) -> None:
    """Require native evidence for the split fault and common-net control."""
    if set(ctx.cases) != set(COMPONENT_REPEATED_SIGNAL_PIN_CASES):
        raise ValueError("Repeated signal-pin fixture set is incomplete")

    fault = ctx.reports[COMPONENT_REPEATED_SIGNAL_PIN_FAULT, "first"]
    observed_fault = ctx.observed_contracts[COMPONENT_REPEATED_SIGNAL_PIN_FAULT, "first"]
    expected_subject = "U1 (Lint:RepeatedSignalPins): repeated READY signal pins use separate nets"
    if (
        fault.status != "REVIEW"
        or {(item.rule_id, item.subject) for item in fault.findings}
        != {(COMPONENT_REPEATED_SIGNAL_PIN_RULE_ID, expected_subject)}
        or observed_fault.component_symbols != {"U1": "Lint:RepeatedSignalPins"}
        or observed_fault.component_pin_numbers != {"U1": ("1", "2", "3", "4")}
        or observed_fault.pin_functions
        != {"U1.1": "READY", "U1.2": "READY", "U1.3": "STATUS", "U1.4": "Pin_4"}
        or observed_fault.pin_electrical_types
        != {"U1.1": "input", "U1.2": "input", "U1.3": "input", "U1.4": "passive"}
        or observed_fault.nets
        != {"SIGNAL_A": ("U1.1",), "SIGNAL_B": ("U1.2",), "STATUS": ("U1.3",)}
    ):
        raise ValueError("Repeated signal-pin fault lost its native lint evidence")

    finding = fault.findings[0]
    if finding.evidence != {
        "U1.1": ("SIGNAL_A",),
        "U1.2": ("SIGNAL_B",),
        "component_symbol": ("Lint:RepeatedSignalPins",),
        "electrical_type": ("input",),
        "pin_function": ("READY",),
    }:
        raise ValueError("Repeated signal-pin fault evidence changed")

    control = ctx.reports[COMPONENT_REPEATED_SIGNAL_PIN_CONTROL, "first"]
    observed_control = ctx.observed_contracts[COMPONENT_REPEATED_SIGNAL_PIN_CONTROL, "first"]
    if (
        control.status != "PASS"
        or control.findings
        or observed_control.nets != {"SIGNAL_A": ("U1.1", "U1.2"), "STATUS": ("U1.3",)}
        or observed_control.pin_functions != observed_fault.pin_functions
        or observed_control.pin_electrical_types != observed_fault.pin_electrical_types
    ):
        raise ValueError("Repeated signal-pin common-net control no longer passes")
