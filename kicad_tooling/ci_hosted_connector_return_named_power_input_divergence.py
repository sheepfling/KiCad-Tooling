"""Verify source-bound native evidence for named connector power-input divergence."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

RULE_ID = "connector.footprint_named_power_input_assignment_divergence"
FAULT_CASE = "footprint-alias-named-power-input-divergence-fault"
CONTROL_CASE = "footprint-alias-named-power-input-divergence-control"


def verify_footprint_alias_named_power_input_divergence(
    ctx: ConnectorReturnFixtureContext,
) -> dict[str, str]:
    """Bind split BIAS_IN assignments to a common-net native control."""
    fault = ctx.reports[FAULT_CASE, "first"]
    observed = ctx.observed_contracts[FAULT_CASE, "first"]
    coverage = fault.connector_peer_pin_coverage
    if (
        fault.status != "REVIEW"
        or coverage is None
        or coverage.netlist_sha256 != ctx.netlist_hashes[FAULT_CASE, "first"]
        or tuple(item.rule_id for item in fault.findings) != (RULE_ID,)
        or observed.components["J1"].part_id is not None
        or observed.components["J2"].part_id is not None
        or observed.components["J1"].value != "Synthetic named power-input peer"
        or observed.components["J2"].value != "Synthetic named power-input peer"
        or observed.components["J1"].footprint != "Synthetic:Package"
        or observed.components["J2"].footprint != "Synthetic:Package"
        or observed.component_symbols["J1"] == observed.component_symbols["J2"]
        or observed.component_pin_numbers["J1"] != ("1", "2")
        or observed.component_pin_numbers["J2"] != ("1", "2")
        or any(
            observed.pin_functions.get(f"{reference}.{number}") != function
            or observed.pin_electrical_types.get(f"{reference}.{number}") != pin_type
            for reference in ("J1", "J2")
            for number, function, pin_type in (
                ("1", "BIAS_IN", "power_in"),
                ("2", "2", "passive"),
            )
        )
    ):
        raise ValueError("Native named power-input divergence fixture lost complete peer evidence")

    alias = coverage.footprint_alias_coverage
    nets = {net: set(pins) for net, pins in observed.nets.items()}
    finding = fault.findings[0]
    if (
        nets.get("BIAS_INPUT_A") != {"J1.1"}
        or nets.get("BIAS_INPUT_B") != {"J2.1"}
        or nets.get("COMMON_ANCHOR") != {"J1.2", "J2.2"}
        or finding.evidence.get("assignments") != ("J1.1=BIAS_INPUT_A", "J2.1=BIAS_INPUT_B")
        or finding.evidence.get("pin_electrical_type") != ("power_in",)
        or finding.evidence.get("common_anchor_pin_numbers") != ("2",)
        or alias.status != "EVALUATED"
        or alias.candidate_group_count != 1
        or alias.eligible_peer_group_count != 1
        or alias.peer_scope_group_count != 1
        or alias.common_anchor_group_count != 1
        or alias.different_assignment_pin_group_count != 1
        or alias.named_power_input_different_assignment_pin_group_count != 1
        or alias.named_power_input_divergence_finding_count != 1
        or alias.unanchored_named_power_input_divergence_pin_group_count != 0
    ):
        raise ValueError("Native named power-input fault lost exact net or coverage evidence")

    control = ctx.reports[CONTROL_CASE, "first"]
    control_observed = ctx.observed_contracts[CONTROL_CASE, "first"]
    control_coverage = control.connector_peer_pin_coverage
    control_alias = None if control_coverage is None else control_coverage.footprint_alias_coverage
    control_nets = {net: set(pins) for net, pins in control_observed.nets.items()}
    if (
        control.status != "PASS"
        or control.findings
        or control_alias is None
        or control_nets.get("BIAS_INPUT") != {"J1.1", "J2.1"}
        or control_nets.get("COMMON_ANCHOR") != {"J1.2", "J2.2"}
        or control_alias.named_power_input_different_assignment_pin_group_count != 0
        or control_alias.named_power_input_divergence_finding_count != 0
    ):
        raise ValueError("Native common-net power-input control did not remain quiet")

    return {
        FAULT_CASE: json.dumps(
            coverage.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    }
