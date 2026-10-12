"""Verify source-bound named connector supply and return pin fixtures."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

NAMED_CONNECTOR_SUPPLY_PIN_CASES = (
    "unconnected-named-supply-fault",
    "unconnected-named-power-control",
)
NAMED_CONNECTOR_RETURN_PIN_CASES = (
    "unconnected-named-return-fault",
    "unconnected-named-power-control",
)
NAMED_CONNECTOR_POWER_PIN_CASES = tuple(
    dict.fromkeys((*NAMED_CONNECTOR_SUPPLY_PIN_CASES, *NAMED_CONNECTOR_RETURN_PIN_CASES))
)


def verify_named_connector_power_pin_cases(ctx: ConnectorReturnFixtureContext) -> None:
    """Verify isolated open VDD/GND contacts and their fully connected control."""
    if not set(ctx.cases) <= set(NAMED_CONNECTOR_POWER_PIN_CASES):
        raise ValueError("Named connector power-pin fixture set contains an unknown case")
    cases = set(ctx.cases)
    if "unconnected-named-power-control" not in cases or not cases.intersection(
        {"unconnected-named-supply-fault", "unconnected-named-return-fault"}
    ):
        raise ValueError("Named connector power-pin fixture set needs a fault and its control")

    expected_functions = {"J1.1": "VDD", "J1.2": "GND"}
    fault_expectations = {
        "unconnected-named-supply-fault": (
            "connector.unconnected_supply_pin",
            "J1.1: VDD",
            "GND",
            ("J1.2",),
        ),
        "unconnected-named-return-fault": (
            "connector.unconnected_return_pin",
            "J1.2: GND",
            "+3V3",
            ("J1.1",),
        ),
    }
    for case, (rule_id, subject, connected_net, connected_pin) in fault_expectations.items():
        if case not in cases:
            continue
        report = ctx.reports[case, "first"]
        observed = ctx.observed_contracts[case, "first"]
        if (
            report.status != "REVIEW"
            or {(item.rule_id, item.subject) for item in report.findings} != {(rule_id, subject)}
            or observed.pin_functions != expected_functions
            or observed.nets.get(connected_net) != connected_pin
        ):
            raise ValueError(f"{case} lost its exact native connector-pin lint evidence")

    control = ctx.reports["unconnected-named-power-control", "first"]
    observed_control = ctx.observed_contracts["unconnected-named-power-control", "first"]
    if (
        control.status != "PASS"
        or control.findings
        or observed_control.pin_functions != expected_functions
        or observed_control.nets.get("+3V3") != ("J1.1",)
        or observed_control.nets.get("GND") != ("J1.2",)
    ):
        raise ValueError("Connected named connector power-pin control no longer passes")
