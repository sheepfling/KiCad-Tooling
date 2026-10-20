"""Verify native evidence for mode-dependent named signals open on peer aliases."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

RULE_ID = "connector.footprint_named_signal_mode_dependent_open_outlier"
FAULT_CASE = "footprint-alias-named-signal-mode-dependent-open-fault"
CONTROL_CASE = "footprint-alias-named-signal-mode-dependent-open-control"


def verify_footprint_alias_named_signal_mode_dependent_open(
    ctx: ConnectorReturnFixtureContext,
) -> dict[str, str]:
    """Bind a partial-open signal prompt to native source and common-net control."""
    fault = ctx.reports[FAULT_CASE, "first"]
    observed = ctx.observed_contracts[FAULT_CASE, "first"]
    coverage = fault.connector_peer_pin_coverage
    if (
        fault.status != "REVIEW"
        or coverage is None
        or coverage.netlist_sha256 != ctx.netlist_hashes[FAULT_CASE, "first"]
        or tuple(item.rule_id for item in fault.findings) != (RULE_ID,)
        or any(
            observed.components[reference].part_id is not None
            or observed.components[reference].value != "Synthetic mode-dependent signal peer"
            or observed.components[reference].footprint != "Synthetic:Package"
            for reference in ("J1", "J2")
        )
        or observed.component_symbols["J1"] == observed.component_symbols["J2"]
        or observed.component_pin_numbers["J1"] != ("1", "2")
        or observed.component_pin_numbers["J2"] != ("1", "2")
        or any(
            observed.pin_functions.get(f"{reference}.{number}") != function
            or observed.pin_electrical_types.get(f"{reference}.{number}") != pin_type
            for reference in ("J1", "J2")
            for number, function, pin_type in (
                ("1", "DATA_IO", "bidirectional"),
                ("2", "2", "passive"),
            )
        )
    ):
        raise ValueError("Native mode-dependent signal fixture lost complete peer evidence")

    alias = coverage.footprint_alias_coverage
    nets = {net: set(pins) for net, pins in observed.nets.items()}
    finding = fault.findings[0]
    if (
        nets.get("DATA_IO") != {"J1.1"}
        or nets.get("COMMON_ANCHOR") != {"J1.2", "J2.2"}
        or finding.evidence.get("assignments") != ("J1.1=DATA_IO", "J2.1=<unassigned>")
        or finding.evidence.get("open_pins") != ("J2.1",)
        or finding.evidence.get("pin_electrical_type") != ("bidirectional",)
        or finding.evidence.get("common_anchor_pin_numbers") != ("2",)
        or alias.open_peer_pin_group_count != 1
        or alias.open_outlier_finding_count != 1
    ):
        raise ValueError("Native mode-dependent signal fault lost exact assignment evidence")

    control = ctx.reports[CONTROL_CASE, "first"]
    control_observed = ctx.observed_contracts[CONTROL_CASE, "first"]
    control_coverage = control.connector_peer_pin_coverage
    control_alias = None if control_coverage is None else control_coverage.footprint_alias_coverage
    control_nets = {net: set(pins) for net, pins in control_observed.nets.items()}
    if (
        control.status != "PASS"
        or control.findings
        or control_alias is None
        or control_nets.get("DATA_IO") != {"J1.1", "J2.1"}
        or control_nets.get("COMMON_ANCHOR") != {"J1.2", "J2.2"}
        or control_alias.open_outlier_finding_count != 0
    ):
        raise ValueError("Native common-net mode-dependent signal control did not remain quiet")

    return {
        case: json.dumps(
            ctx.reports[case, "first"].connector_peer_pin_coverage.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        for case in (FAULT_CASE, CONTROL_CASE)
    }
