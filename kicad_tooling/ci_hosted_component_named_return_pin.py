"""Verify the native named return-pin fault and assigned control."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

COMPONENT_NAMED_RETURN_PIN_CASES = (
    "unconnected-named-component-return-fault",
    "unconnected-named-component-power-control",
    "split-named-component-return-fault",
    "common-named-component-return-control",
)


def verify_component_named_return_pin_cases(ctx: ConnectorReturnFixtureContext) -> None:
    """Check native named-return and split-return evidence with quiet controls."""
    if set(ctx.cases) != set(COMPONENT_NAMED_RETURN_PIN_CASES):
        raise ValueError("Named component return-pin fixture set is incomplete")

    fault = ctx.reports["unconnected-named-component-return-fault", "first"]
    observed_fault = ctx.observed_contracts["unconnected-named-component-return-fault", "first"]
    if (
        fault.status != "REVIEW"
        or {(item.rule_id, item.subject) for item in fault.findings}
        != {("component.unconnected_return_pin", "U1.2: GND")}
        or observed_fault.component_symbols != {"U1": "Lint:PowerRoleComponent"}
        or observed_fault.pin_functions != {"U1.1": "VDD", "U1.2": "GND"}
        or observed_fault.nets.get("+3V3") != ("U1.1",)
    ):
        raise ValueError("Named component return-pin fault lost its native lint evidence")

    control = ctx.reports["unconnected-named-component-power-control", "first"]
    observed_control = ctx.observed_contracts["unconnected-named-component-power-control", "first"]
    if (
        control.status != "PASS"
        or control.findings
        or observed_control.pin_functions != {"U1.1": "VDD", "U1.2": "GND"}
        or observed_control.nets.get("+3V3") != ("U1.1",)
        or observed_control.nets.get("GND") != ("U1.2",)
    ):
        raise ValueError("Named component return-pin control no longer passes")

    split = ctx.reports["split-named-component-return-fault", "first"]
    observed_split = ctx.observed_contracts["split-named-component-return-fault", "first"]
    if (
        split.status != "REVIEW"
        or {(item.rule_id, item.subject) for item in split.findings}
        != {
            (
                "component.repeated_return_pin_function",
                "U1 (Lint:MultiReturnComponent): return pins use distinct nets",
            )
        }
        or observed_split.component_symbols != {"U1": "Lint:MultiReturnComponent"}
        or observed_split.pin_functions != {"U1.1": "GND", "U1.2": "AGND"}
        or observed_split.nets != {"RETURN_A": ("U1.1",), "RETURN_B": ("U1.2",)}
    ):
        raise ValueError("Split component return-pin fault lost its native lint evidence")

    common = ctx.reports["common-named-component-return-control", "first"]
    observed_common = ctx.observed_contracts["common-named-component-return-control", "first"]
    if (
        common.status != "PASS"
        or common.findings
        or observed_common.nets.get("RETURN") != ("U1.1", "U1.2")
        or observed_common.pin_functions != {"U1.1": "GND", "U1.2": "AGND"}
    ):
        raise ValueError("Common component return-pin control no longer passes")
