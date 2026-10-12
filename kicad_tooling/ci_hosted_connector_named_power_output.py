"""Validate native fixtures for named connector power-output aliases."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

CASES = (
    "connector-named-power-output-open-fault",
    "connector-named-power-output-open-control",
    "connector-named-power-output-all-open-fault",
)
RULE_ID = "connector.peer_power_output_open_assignment"
ALL_OPEN_RULE_ID = "connector.peer_power_output_named_all_open"


def verify_connector_named_power_output_cases(ctx: ConnectorReturnFixtureContext) -> None:
    """Check native alias metadata and mixed/all-open fault-control cases."""
    if set(ctx.cases) != set(CASES):
        raise ValueError("Connector named power-output fixture set is incomplete")

    fault_case, control_case, all_open_case = CASES
    fault = ctx.reports[fault_case, "first"]
    observed_fault = ctx.observed_contracts[fault_case, "first"]
    findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
    if (
        len(findings) != 1
        or findings[0].evidence.get("J1.1") != ("+3V3",)
        or findings[0].evidence.get("J2.1") != ()
        or observed_fault.component_symbols
        != {
            "J1": "Lint:NamedPeerPowerOutputA",
            "J2": "Lint:NamedPeerPowerOutputB",
        }
        or any(
            observed_fault.components[reference].part_id != "SYNTHETIC-CONNECTOR-NAMED-OUTPUT-001"
            for reference in ("J1", "J2")
        )
        or observed_fault.component_pin_numbers != {"J1": ("1", "2"), "J2": ("1", "2")}
        or any(
            observed_fault.pin_functions.get(f"{reference}.1") != "BIAS_OUT"
            for reference in ("J1", "J2")
        )
        or any(
            observed_fault.pin_electrical_types.get(f"{reference}.1") != "power_out"
            for reference in ("J1", "J2")
        )
    ):
        raise ValueError("Connector named power-output alias fault lost native lint evidence")

    control = ctx.reports[control_case, "first"]
    observed_control = ctx.observed_contracts[control_case, "first"]
    if any(item.rule_id in {RULE_ID, ALL_OPEN_RULE_ID} for item in control.findings) or (
        observed_control.nets.get("+3V3") != ("J1.1", "J2.1")
    ):
        raise ValueError(
            "Connector named power-output common-net control changed its target-rule outcome: "
            f"findings={tuple(item.rule_id for item in control.findings)}, "
            f"assignments={observed_control.nets.get('+3V3')}"
        )

    all_open = ctx.reports[all_open_case, "first"]
    observed_all_open = ctx.observed_contracts[all_open_case, "first"]
    all_open_findings = tuple(
        item for item in all_open.findings if item.rule_id == ALL_OPEN_RULE_ID
    )
    if (
        len(all_open_findings) != 1
        or all_open_findings[0].evidence.get("J1.1") != ()
        or all_open_findings[0].evidence.get("J2.1") != ()
        or any(item.rule_id == RULE_ID for item in all_open.findings)
        or observed_all_open.component_symbols
        != {
            "J1": "Lint:NamedPeerPowerOutputA",
            "J2": "Lint:NamedPeerPowerOutputB",
        }
        or any(
            observed_all_open.components[reference].part_id
            != "SYNTHETIC-CONNECTOR-NAMED-OUTPUT-001"
            for reference in ("J1", "J2")
        )
        or observed_all_open.component_pin_numbers != {"J1": ("1", "2"), "J2": ("1", "2")}
        or any(
            observed_all_open.pin_functions.get(f"{reference}.1") != "BIAS_OUT"
            for reference in ("J1", "J2")
        )
        or any(
            observed_all_open.pin_electrical_types.get(f"{reference}.1") != "power_out"
            for reference in ("J1", "J2")
        )
        or observed_all_open.nets.get("SIGNAL") != ("J1.2", "J2.2")
    ):
        raise ValueError("Connector all-open power-output alias fault lost native lint evidence")
