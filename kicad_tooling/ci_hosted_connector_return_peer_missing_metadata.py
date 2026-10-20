"""Verify native evidence for split connector peers with missing pin metadata."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext
from .hwrepo.connector_identity import native_pin_metadata_is_missing

RULE_ID = "connector.footprint_peer_pin_missing_metadata_assignment_divergence"
FAULT_CASE = "footprint-alias-peer-missing-metadata-fault"
CONTROL_CASE = "footprint-alias-peer-missing-metadata-control"
PART_ID_FAULT_CASE = "footprint-alias-part-id-peer-missing-metadata-fault"
PART_ID_CONTROL_CASE = "footprint-alias-part-id-peer-missing-metadata-control"


def verify_footprint_alias_peer_missing_metadata_divergence(
    ctx: ConnectorReturnFixtureContext,
) -> dict[str, str]:
    """Bind an unnamed split pin and common-net control to exact native exports."""
    fault = ctx.reports[FAULT_CASE, "first"]
    observed = ctx.observed_contracts[FAULT_CASE, "first"]
    coverage = fault.connector_peer_pin_coverage
    findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
    if (
        fault.status != "REVIEW"
        or coverage is None
        or coverage.netlist_sha256 != ctx.netlist_hashes[FAULT_CASE, "first"]
        or len(findings) != 1
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
        or not native_pin_metadata_is_missing(observed.pin_functions.get("J2.1"))
        or observed.pin_electrical_types.get("J1.1") != "input"
        or observed.pin_electrical_types.get("J2.1") != "output"
        or any(
            observed.pin_functions.get(f"{reference}.2") != "2"
            or observed.pin_electrical_types.get(f"{reference}.2") != "passive"
            for reference in ("J1", "J2")
        )
    ):
        raise ValueError("Native missing-metadata fixture lost complete peer evidence")

    nets = {net: set(pins) for net, pins in observed.nets.items()}
    finding = findings[0]
    alias = coverage.footprint_alias_coverage
    if (
        nets.get("UART_RX_NET") != {"J1.1"}
        or nets.get("UART_TX_NET") != {"J2.1"}
        or nets.get("COMMON_REFERENCE") != {"J1.2", "J2.2"}
        or finding.evidence.get("pin_number") != ("1",)
        or finding.evidence.get("missing_metadata") != ("J2.1: pin_function",)
        or finding.evidence.get("assignments") != ("J1.1=UART_RX_NET", "J2.1=UART_TX_NET")
        or finding.evidence.get("common_anchor_pin_numbers") != ("2",)
        or alias.candidate_group_count != 1
        or alias.incomplete_pin_inventory_group_count != 0
        or alias.incomplete_pin_metadata_group_count != 1
        or alias.eligible_peer_group_count != 0
        or any(
            item.rule_id == "connector.footprint_peer_pin_metadata_assignment_divergence"
            for item in fault.findings
        )
    ):
        raise ValueError("Native missing-metadata fault lost its exact assignment evidence")

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
        or control_alias.incomplete_pin_metadata_group_count != 1
    ):
        raise ValueError("Native common-assignment control produced a missing-metadata finding")

    part_id_fault = ctx.reports[PART_ID_FAULT_CASE, "first"]
    part_id_observed = ctx.observed_contracts[PART_ID_FAULT_CASE, "first"]
    part_id_findings = tuple(item for item in part_id_fault.findings if item.rule_id == RULE_ID)
    part_ids = (
        part_id_observed.components["J1"].part_id,
        part_id_observed.components["J2"].part_id,
    )
    part_id_nets = {net: set(pins) for net, pins in part_id_observed.nets.items()}
    if (
        part_id_fault.status != "REVIEW"
        or len(part_id_findings) != 1
        or tuple(value.casefold() for value in part_ids if value is not None)
        != ("synthetic-peer-001", "synthetic-peer-001")
        or part_ids != ("SYNTHETIC-PEER-001", "synthetic-peer-001")
        or part_id_findings[0].evidence.get("peer_identity_basis") != ("part_id",)
        or part_id_findings[0].evidence.get("assignments")
        != ("J1.1=UART_RX_NET", "J2.1=UART_TX_NET")
        or part_id_findings[0].evidence.get("common_anchor_pin_numbers") != ("2",)
        or part_id_nets.get("COMMON_REFERENCE") != {"J1.2", "J2.2"}
    ):
        raise ValueError("Native matching-PART_ID fault lost its split assignment evidence")

    part_id_control = ctx.reports[PART_ID_CONTROL_CASE, "first"]
    part_id_control_observed = ctx.observed_contracts[PART_ID_CONTROL_CASE, "first"]
    part_id_control_nets = {net: set(pins) for net, pins in part_id_control_observed.nets.items()}
    if (
        any(item.rule_id == RULE_ID for item in part_id_control.findings)
        or part_id_control_nets.get("SHARED_PORT") != {"J1.1", "J2.1"}
        or part_id_control_nets.get("COMMON_REFERENCE") != {"J1.2", "J2.2"}
    ):
        raise ValueError("Native matching-PART_ID common-net control produced a finding")

    return {
        FAULT_CASE: json.dumps(
            finding.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ),
        PART_ID_FAULT_CASE: json.dumps(
            part_id_findings[0].model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ),
    }
