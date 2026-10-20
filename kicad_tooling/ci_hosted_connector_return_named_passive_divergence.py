"""Verify source-bound native evidence for named connector passive divergence."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

RULE_ID = "connector.footprint_named_passive_assignment_divergence"
FAULT_CASE = "footprint-alias-named-passive-divergence-fault"
CONTROL_CASE = "footprint-alias-named-passive-divergence-control"


def verify_footprint_alias_named_passive_divergence(
    ctx: ConnectorReturnFixtureContext,
) -> dict[str, str]:
    """Bind split AUX_DETECT assignments to a common-net native control."""
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
        or observed.components["J1"].value != "Synthetic named passive peer"
        or observed.components["J2"].value != "Synthetic named passive peer"
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
                ("1", "AUX_DETECT", "passive"),
                ("2", "2", "passive"),
            )
        )
    ):
        raise ValueError("Native named passive divergence fixture lost complete peer evidence")

    alias = coverage.footprint_alias_coverage
    nets = {net: set(pins) for net, pins in observed.nets.items()}
    finding = fault.findings[0]
    if (
        nets.get("AUX_DETECT_A") != {"J1.1"}
        or nets.get("AUX_DETECT_B") != {"J2.1"}
        or nets.get("COMMON_ANCHOR") != {"J1.2", "J2.2"}
        or finding.evidence.get("assignments") != ("J1.1=AUX_DETECT_A", "J2.1=AUX_DETECT_B")
        or finding.evidence.get("pin_electrical_type") != ("passive",)
        or finding.evidence.get("common_anchor_pin_numbers") != ("2",)
        or alias.status != "EVALUATED"
        or alias.candidate_group_count != 1
        or alias.eligible_peer_group_count != 1
        or alias.peer_scope_group_count != 1
        or alias.common_anchor_group_count != 1
        or alias.different_assignment_pin_group_count != 1
        or alias.named_passive_different_assignment_pin_group_count != 1
        or alias.named_passive_divergence_finding_count != 1
        or alias.unanchored_named_passive_divergence_pin_group_count != 0
    ):
        raise ValueError("Native named passive fault lost exact net or coverage evidence")

    control = ctx.reports[CONTROL_CASE, "first"]
    control_observed = ctx.observed_contracts[CONTROL_CASE, "first"]
    control_coverage = control.connector_peer_pin_coverage
    control_alias = None if control_coverage is None else control_coverage.footprint_alias_coverage
    control_nets = {net: set(pins) for net, pins in control_observed.nets.items()}
    if (
        control.status != "PASS"
        or control.findings
        or control_alias is None
        or control_nets.get("AUX_DETECT") != {"J1.1", "J2.1"}
        or control_nets.get("COMMON_ANCHOR") != {"J1.2", "J2.2"}
        or control_alias.named_passive_different_assignment_pin_group_count != 0
        or control_alias.named_passive_divergence_finding_count != 0
    ):
        raise ValueError("Native common-net passive control did not remain quiet")

    return {
        FAULT_CASE: json.dumps(
            coverage.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    }
