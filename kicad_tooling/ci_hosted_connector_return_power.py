"""Verify connector power input and numbered channel rail fixtures."""

from __future__ import annotations

from .ci_hosted_component_power_input import verify_generic_component_power_input_cases
from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def verify_connector_power_inputs(ctx: ConnectorReturnFixtureContext):
    """Verify connector power input and numbered channel rail fixtures."""
    generic_power_fault = ctx.reports["unconnected-generic-power-input-fault", "first"]
    generic_power_control = ctx.reports["unconnected-generic-power-input-control", "first"]
    expected_generic_power_subjects = {
        "J1.1: generic native power-input pin is unassigned",
        "J2.1: generic native power-input pin is unassigned",
    }
    if (
        generic_power_fault.status != "REVIEW"
        or {item.rule_id for item in generic_power_fault.findings}
        != {"connector.unconnected_power_input"}
        or {item.subject for item in generic_power_fault.findings}
        != expected_generic_power_subjects
        or (generic_power_control.status != "PASS")
        or generic_power_control.findings
        or (
            ctx.observed_contracts[
                "unconnected-generic-power-input-fault", "first"
            ].pin_electrical_types
            != {"J1.1": "power_in", "J1.2": "passive", "J2.1": "power_in", "J2.2": "passive"}
        )
        or (
            ctx.observed_contracts["unconnected-generic-power-input-control", "first"].nets.get(
                "+5V"
            )
            != ("J1.1", "J2.1")
        )
    ):
        raise ValueError(
            "Generic connector power-input fixture lost its exact native fault/control result"
        )
    verify_generic_component_power_input_cases(ctx)
    channel_fault = ctx.reports["channel-power-fault", "first"]
    channel_fault_rails = next(
        (
            finding
            for finding in channel_fault.findings
            if finding.rule_id == "net.numbered_power_rails"
        ),
        None,
    )
    if (
        channel_fault.status != "REVIEW"
        or channel_fault_rails is None
        or channel_fault_rails.subject != "CH VDD"
        or (dict(channel_fault_rails.evidence) != {"CH2_VDD": ("J1.3",), "CH3_VDD": ("J2.3",)})
    ):
        raise ValueError("Channel-prefixed power-name fault lost its exact native lint evidence")
    channel_control = ctx.reports["channel-power-control", "first"]
    if channel_control.status != "PASS" or channel_control.findings:
        raise ValueError("Common channel-prefixed supply control no longer passes")
    if ctx.observed_contracts["channel-power-control", "first"].nets.get("CH2_VDD") != (
        "J1.3",
        "J2.3",
    ):
        raise ValueError("Channel-prefixed common-net control lost its native connector pins")
