"""Verify native evidence for open connector peer pins with missing metadata."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext
from .hwrepo.connector_identity import native_pin_metadata_is_missing

RULE_ID = "connector.footprint_peer_pin_missing_metadata_open_outlier"
FAULT_CASE = "footprint-alias-peer-missing-metadata-open-fault"
CONTROL_CASE = "footprint-alias-peer-missing-metadata-open-control"


def verify_footprint_alias_peer_missing_metadata_open_outlier(
    ctx: ConnectorReturnFixtureContext,
) -> dict[str, str]:
    """Bind the open-peer finding and common-assignment control to native exports."""
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
        or observed.pin_electrical_types.get("J2.1") != "input"
    ):
        raise ValueError("Native missing-metadata open fixture lost its complete peer evidence")

    nets = {net: set(pins) for net, pins in observed.nets.items()}
    finding = findings[0]
    if (
        nets.get("UART_RX_NET") != {"J1.1"}
        or nets.get("COMMON_REFERENCE") != {"J1.2", "J2.2"}
        or finding.evidence.get("pin_number") != ("1",)
        or finding.evidence.get("missing_metadata") != ("J2.1: pin_function",)
        or finding.evidence.get("assignments") != ("J1.1=UART_RX_NET", "J2.1=<unassigned>")
        or finding.evidence.get("common_anchor_pin_numbers") != ("2",)
        or any(
            item.rule_id == "connector.footprint_peer_pin_missing_metadata_assignment_divergence"
            for item in fault.findings
        )
    ):
        raise ValueError("Native missing-metadata open fault lost its exact pin evidence")

    control = ctx.reports[CONTROL_CASE, "first"]
    control_observed = ctx.observed_contracts[CONTROL_CASE, "first"]
    control_nets = {net: set(pins) for net, pins in control_observed.nets.items()}
    if (
        any(item.rule_id == RULE_ID for item in control.findings)
        or control_nets.get("SHARED_PORT") != {"J1.1", "J2.1"}
        or control_nets.get("COMMON_REFERENCE") != {"J1.2", "J2.2"}
    ):
        raise ValueError("Native common-assignment control produced an open-metadata finding")

    return {
        FAULT_CASE: json.dumps(
            finding.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    }
