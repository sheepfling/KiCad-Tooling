"""Verify native fixtures for generic peer power-input assignment review."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

COMPONENT_PEER_POWER_INPUT_CASES = (
    "peer-generic-power-input-fault",
    "peer-generic-power-input-control",
)
RULE_ID = "component.peer_power_input_assignment_divergence"
NAMED_COMPONENT_PEER_POWER_INPUT_OPEN_CASES = (
    "peer-named-power-input-open-fault",
    "peer-named-power-input-open-control",
)
NAMED_COMPONENT_PEER_POWER_INPUT_OPEN_RULE_ID = "component.peer_power_input_open_assignment"


def verify_component_peer_power_input_cases(ctx: ConnectorReturnFixtureContext) -> None:
    """Check that the split generic power-input fault is reported and control is clear."""
    if set(ctx.cases) != set(COMPONENT_PEER_POWER_INPUT_CASES):
        raise ValueError("Generic peer power-input fixture set is incomplete")

    fault_case, control_case = COMPONENT_PEER_POWER_INPUT_CASES
    fault = ctx.reports[fault_case, "first"]
    observed_fault = ctx.observed_contracts[fault_case, "first"]
    findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
    if (
        fault.status != "REVIEW"
        or len(findings) != 1
        or findings[0].evidence.get("U1.1") != ("SYNTHETIC_RAIL_A",)
        or findings[0].evidence.get("U2.1") != ("SYNTHETIC_RAIL_B",)
        or observed_fault.component_symbols
        != {"U1": "Lint:GenericPowerInputPeer", "U2": "Lint:GenericPowerInputPeer"}
        or observed_fault.component_pin_numbers != {"U1": ("1", "2"), "U2": ("1", "2")}
        or observed_fault.pin_electrical_types.get("U1.1") != "power_in"
        or observed_fault.pin_electrical_types.get("U2.1") != "power_in"
    ):
        raise ValueError("Generic peer power-input fault lost its native lint evidence")

    control = ctx.reports[control_case, "first"]
    observed_control = ctx.observed_contracts[control_case, "first"]
    if (
        control.status != "REVIEW"
        or any(item.rule_id == RULE_ID for item in control.findings)
        or observed_control.nets.get("+3V3") != ("U1.1", "U2.1")
    ):
        raise ValueError(
            "Generic peer power-input common-rail control changed its target-rule outcome: "
            f"status={control.status}, findings={tuple(item.rule_id for item in control.findings)}, "
            f"assignments={observed_control.nets.get('+3V3')}"
        )


def verify_named_component_peer_power_input_open_cases(
    ctx: ConnectorReturnFixtureContext,
) -> None:
    """Check the named open-peer fault and its assigned control using native evidence."""
    if set(ctx.cases) != set(NAMED_COMPONENT_PEER_POWER_INPUT_OPEN_CASES):
        raise ValueError("Named peer power-input open fixture set is incomplete")

    fault_case, control_case = NAMED_COMPONENT_PEER_POWER_INPUT_OPEN_CASES
    fault = ctx.reports[fault_case, "first"]
    observed_fault = ctx.observed_contracts[fault_case, "first"]
    findings = tuple(
        item
        for item in fault.findings
        if item.rule_id == NAMED_COMPONENT_PEER_POWER_INPUT_OPEN_RULE_ID
    )
    if (
        fault.status != "REVIEW"
        or len(findings) != 1
        or findings[0].evidence.get("U1.1") != ("SYNTHETIC_RAIL_A",)
        or findings[0].evidence.get("U2.1") != ()
        or observed_fault.component_symbols
        != {"U1": "Lint:NamedPeerPowerInput", "U2": "Lint:NamedPeerPowerInput"}
        or observed_fault.component_pin_numbers != {"U1": ("1", "2"), "U2": ("1", "2")}
        or observed_fault.pin_functions.get("U1.1") != "BIAS_IN"
        or observed_fault.pin_functions.get("U2.1") != "BIAS_IN"
        or observed_fault.pin_electrical_types.get("U1.1") != "power_in"
        or observed_fault.pin_electrical_types.get("U2.1") != "power_in"
    ):
        raise ValueError("Named peer power-input open fault lost its native lint evidence")

    control = ctx.reports[control_case, "first"]
    observed_control = ctx.observed_contracts[control_case, "first"]
    if (
        control.status != "REVIEW"
        or any(
            item.rule_id == NAMED_COMPONENT_PEER_POWER_INPUT_OPEN_RULE_ID
            for item in control.findings
        )
        or observed_control.nets.get("+3V3") != ("U1.1", "U2.1")
    ):
        raise ValueError(
            "Named peer power-input assigned control changed its target-rule outcome: "
            f"status={control.status}, findings={tuple(item.rule_id for item in control.findings)}, "
            f"assignments={observed_control.nets.get('+3V3')}"
        )
