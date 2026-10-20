"""Verify source-bound native evidence for named connector signal divergence."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

RULE_ID = "connector.footprint_named_signal_assignment_divergence"
FAULT_CASE = "footprint-alias-named-signal-divergence-fault"
CONTROL_CASE = "footprint-alias-named-signal-output-control"


def verify_footprint_alias_named_signal_divergence(
    ctx: ConnectorReturnFixtureContext,
) -> dict[str, str]:
    """Bind a split UART_TX net fault to a common-net native control."""
    fault = ctx.reports[FAULT_CASE, "first"]
    fault_observed = ctx.observed_contracts[FAULT_CASE, "first"]
    fault_coverage = fault.connector_peer_pin_coverage
    if (
        fault.status != "REVIEW"
        or fault_coverage is None
        or fault_coverage.netlist_sha256 != ctx.netlist_hashes[FAULT_CASE, "first"]
        or len(fault.findings) != 1
        or fault.findings[0].rule_id != RULE_ID
        or fault_observed.components["J1"].part_id is not None
        or fault_observed.components["J2"].part_id is not None
        or fault_observed.components["J1"].value != "Synthetic named signal-output peer"
        or fault_observed.components["J2"].value != "Synthetic named signal-output peer"
        or fault_observed.components["J1"].footprint != "Synthetic:Package"
        or fault_observed.components["J2"].footprint != "Synthetic:Package"
        or fault_observed.component_symbols["J1"] == fault_observed.component_symbols["J2"]
        or fault_observed.component_pin_numbers["J1"] != ("1", "2")
        or fault_observed.component_pin_numbers["J2"] != ("1", "2")
        or any(
            fault_observed.pin_functions.get(f"{reference}.{number}") != function
            or fault_observed.pin_electrical_types.get(f"{reference}.{number}") != pin_type
            for reference in ("J1", "J2")
            for number, function, pin_type in (
                ("1", "UART_TX", "output"),
                ("2", "2", "passive"),
            )
        )
    ):
        raise ValueError("Native named signal-divergence fixture lost complete peer evidence")

    fault_alias = fault_coverage.footprint_alias_coverage
    fault_nets = {net: set(pins) for net, pins in fault_observed.nets.items()}
    if (
        fault_nets.get("UART_TX_A") != {"J1.1"}
        or fault_nets.get("UART_TX_B") != {"J2.1"}
        or fault_nets.get("COMMON_ANCHOR") != {"J1.2", "J2.2"}
        or fault.findings[0].evidence.get("assignments") != ("J1.1=UART_TX_A", "J2.1=UART_TX_B")
        or fault.findings[0].evidence.get("common_anchor_pin_numbers") != ("2",)
        or fault_alias.status != "EVALUATED"
        or fault_alias.candidate_group_count != 1
        or fault_alias.eligible_peer_group_count != 1
        or fault_alias.peer_scope_group_count != 1
        or fault_alias.common_anchor_group_count != 1
        or fault_alias.different_assignment_pin_group_count != 1
        or fault_alias.named_signal_different_assignment_pin_group_count != 1
        or fault_alias.named_signal_divergence_finding_count != 1
        or fault_alias.unanchored_named_signal_divergence_pin_group_count != 0
    ):
        raise ValueError("Native named signal-divergence fault lost exact net or coverage evidence")

    control = ctx.reports[CONTROL_CASE, "first"]
    control_observed = ctx.observed_contracts[CONTROL_CASE, "first"]
    control_coverage = control.connector_peer_pin_coverage
    control_alias = None if control_coverage is None else control_coverage.footprint_alias_coverage
    control_nets = {net: set(pins) for net, pins in control_observed.nets.items()}
    if (
        control.status != "PASS"
        or control.findings
        or control_alias is None
        or control_nets.get("UART_TX") != {"J1.1", "J2.1"}
        or control_nets.get("COMMON_ANCHOR") != {"J1.2", "J2.2"}
        or control_alias.named_signal_different_assignment_pin_group_count != 0
        or control_alias.named_signal_divergence_finding_count != 0
    ):
        raise ValueError("Native common-net signal control did not remain quiet")

    return {
        FAULT_CASE: json.dumps(
            fault_coverage.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    }
