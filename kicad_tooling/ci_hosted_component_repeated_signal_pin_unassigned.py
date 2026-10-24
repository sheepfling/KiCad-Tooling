"""Verify exact native evidence for an open repeated signal-function pin."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext
from .hwrepo.design_lint_rule_types import DesignLintRuleId

COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_FAULT = "repeated-signal-pin-unassigned-fault"
COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_CONTROL = "repeated-signal-pin-unassigned-control"
COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_CASES = (
    COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_FAULT,
    COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_CONTROL,
)
COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_RULE_ID: DesignLintRuleId = (
    "component.repeated_signal_pin_unassigned"
)


def verify_component_repeated_signal_pin_unassigned_cases(
    ctx: ConnectorReturnFixtureContext,
) -> None:
    """Require exact native pin metadata and a quiet common-net control."""
    if set(ctx.cases) != set(COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_CASES):
        raise ValueError("Repeated signal-pin unassigned fixture set is incomplete")

    fault_case = COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_FAULT
    fault = ctx.reports[fault_case, "first"]
    observed = ctx.observed_contracts[fault_case, "first"]
    expected_subject = (
        "U1 (Lint:RepeatedSignalPins): repeated READY signal pins include an unassigned pin"
    )
    open_pins = {pin for pins in observed.unconnected_nets.values() for pin in pins}
    if (
        fault.status != "REVIEW"
        or {(item.rule_id, item.subject) for item in fault.findings}
        != {(COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_RULE_ID, expected_subject)}
        or observed.component_symbols != {"U1": "Lint:RepeatedSignalPins"}
        or observed.component_pin_numbers != {"U1": ("1", "2", "3", "4")}
        or observed.pin_functions
        != {"U1.1": "READY", "U1.2": "READY", "U1.3": "STATUS", "U1.4": "Pin_4"}
        or observed.pin_electrical_types
        != {"U1.1": "input", "U1.2": "input", "U1.3": "input", "U1.4": "passive"}
        or observed.nets != {"SIGNAL_A": ("U1.1",), "STATUS": ("U1.3",)}
        or "U1.2" not in open_pins
    ):
        raise ValueError("Repeated signal-pin unassigned fault lost its native evidence")

    finding = fault.findings[0]
    if finding.evidence != {
        "U1.1": ("SIGNAL_A",),
        "U1.2": (),
        "assigned_signal_pins": ("U1.1",),
        "component_symbol": ("Lint:RepeatedSignalPins",),
        "electrical_type": ("input",),
        "pin_function": ("READY",),
        "unassigned_signal_pins": ("U1.2",),
    }:
        raise ValueError("Repeated signal-pin unassigned evidence changed")

    control_case = COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_CONTROL
    control = ctx.reports[control_case, "first"]
    observed_control = ctx.observed_contracts[control_case, "first"]
    if (
        control.status != "PASS"
        or control.findings
        or observed_control.nets != {"SIGNAL_A": ("U1.1", "U1.2"), "STATUS": ("U1.3",)}
        or observed_control.pin_functions != observed.pin_functions
        or observed_control.pin_electrical_types != observed.pin_electrical_types
    ):
        raise ValueError("Repeated signal-pin common-net control no longer passes")
