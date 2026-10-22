"""Verify native evidence for connector peer pin-metadata assignment review."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

RULE_ID = "connector.footprint_peer_pin_metadata_assignment_divergence"
FAULT_CASE = "footprint-alias-peer-metadata-fault"
CONTROL_CASE = "footprint-alias-peer-metadata-control"


def verify_footprint_alias_peer_metadata_divergence(
    ctx: ConnectorReturnFixtureContext,
) -> dict[str, str]:
    """Bind the metadata-mismatch split and common-net control to native exports."""
    fault = ctx.reports[FAULT_CASE, "first"]
    observed = ctx.observed_contracts[FAULT_CASE, "first"]
    coverage = fault.connector_peer_pin_coverage
    matching_findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
    if (
        fault.status != "REVIEW"
        or coverage is None
        or coverage.netlist_sha256 != ctx.netlist_hashes[FAULT_CASE, "first"]
        or len(matching_findings) != 1
        or observed.components["J1"].part_id is not None
        or observed.components["J2"].part_id is not None
        or observed.components["J1"].value != "Synthetic peer metadata connector"
        or observed.components["J2"].value != "Synthetic peer metadata connector"
        or observed.components["J1"].footprint != "Synthetic:Package"
        or observed.components["J2"].footprint != "Synthetic:Package"
        or observed.component_symbols["J1"] == observed.component_symbols["J2"]
        or observed.component_pin_numbers["J1"] != ("1", "2")
        or observed.component_pin_numbers["J2"] != ("1", "2")
        or observed.pin_functions.get("J1.1") != "UART_RX"
        or observed.pin_electrical_types.get("J1.1") != "input"
        or observed.pin_functions.get("J2.1") != "UART_TX"
        or observed.pin_electrical_types.get("J2.1") != "output"
        or any(
            observed.pin_functions.get(f"{reference}.2") != "2"
            or observed.pin_electrical_types.get(f"{reference}.2") != "passive"
            for reference in ("J1", "J2")
        )
    ):
        raise ValueError("Native metadata-divergence fixture lost complete peer evidence")

    nets = {net: set(pins) for net, pins in observed.nets.items()}
    finding = matching_findings[0]
    alias = coverage.footprint_alias_coverage
    if (
        nets.get("UART_RX_NET") != {"J1.1"}
        or nets.get("UART_TX_NET") != {"J2.1"}
        or nets.get("COMMON_REFERENCE") != {"J1.2", "J2.2"}
        or finding.evidence.get("pin_number") != ("1",)
        or finding.evidence.get("metadata_mismatch_fields")
        != ("pin_function", "pin_electrical_type")
        or finding.evidence.get("assignments") != ("J1.1=UART_RX_NET", "J2.1=UART_TX_NET")
        or finding.evidence.get("common_anchor_pin_numbers") != ("2",)
        or alias.candidate_group_count != 1
        or alias.incomplete_pin_inventory_group_count != 0
        or alias.incomplete_pin_metadata_group_count != 0
        or alias.differing_pin_metadata_group_count != 1
        or alias.eligible_peer_group_count != 0
    ):
        raise ValueError("Native metadata-divergence fault lost its exact assignment evidence")

    control = ctx.reports[CONTROL_CASE, "first"]
    control_observed = ctx.observed_contracts[CONTROL_CASE, "first"]
    control_coverage = control.connector_peer_pin_coverage
    control_alias = None if control_coverage is None else control_coverage.footprint_alias_coverage
    control_nets = {net: set(pins) for net, pins in control_observed.nets.items()}
    if (
        any(item.rule_id == RULE_ID for item in control.findings)
        or control_alias is None
        or control_nets.get("SHARED_PORT") != {"J1.1", "J2.1"}
        or control_nets.get("COMMON_REFERENCE") != {"J1.2", "J2.2"}
        or control_alias.incomplete_pin_metadata_group_count != 0
        or control_alias.differing_pin_metadata_group_count != 1
    ):
        raise ValueError("Native common-target control produced a metadata-divergence finding")

    return {
        FAULT_CASE: json.dumps(
            coverage.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    }
