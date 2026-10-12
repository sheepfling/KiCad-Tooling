"""Verify native connector named power-input alias fixtures."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

CASES = (
    "connector-named-power-input-open-fault",
    "connector-named-power-input-open-control",
)
RULE_ID = "connector.peer_power_input_open_assignment"


def verify_connector_named_power_input_cases(ctx: ConnectorReturnFixtureContext) -> None:
    """Check alias identity, native pin metadata, and the fault/control result."""
    if set(ctx.cases) != set(CASES):
        raise ValueError("Connector named power-input fixture set is incomplete")

    fault_case, control_case = CASES
    fault = ctx.reports[fault_case, "first"]
    observed_fault = ctx.observed_contracts[fault_case, "first"]
    findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
    if (
        len(findings) != 1
        or findings[0].evidence.get("J1.1") != ("+3V3",)
        or findings[0].evidence.get("J2.1") != ()
        or observed_fault.component_symbols
        != {
            "J1": "Lint:NamedPeerPowerInputA",
            "J2": "Lint:NamedPeerPowerInputB",
        }
        or any(
            observed_fault.components[reference].part_id != "SYNTHETIC-CONNECTOR-NAMED-INPUT-001"
            for reference in ("J1", "J2")
        )
        or observed_fault.component_pin_numbers != {"J1": ("1", "2"), "J2": ("1", "2")}
        or any(
            observed_fault.pin_functions.get(f"{reference}.1") != "BIAS_IN"
            for reference in ("J1", "J2")
        )
        or any(
            observed_fault.pin_electrical_types.get(f"{reference}.1") != "power_in"
            for reference in ("J1", "J2")
        )
    ):
        raise ValueError("Connector named power-input alias fault lost native lint evidence")

    control = ctx.reports[control_case, "first"]
    observed_control = ctx.observed_contracts[control_case, "first"]
    if any(item.rule_id == RULE_ID for item in control.findings) or observed_control.nets.get(
        "+3V3"
    ) != ("J1.1", "J2.1"):
        raise ValueError(
            "Connector named power-input common-net control changed its target-rule outcome: "
            f"findings={tuple(item.rule_id for item in control.findings)}, "
            f"assignments={observed_control.nets.get('+3V3')}"
        )
