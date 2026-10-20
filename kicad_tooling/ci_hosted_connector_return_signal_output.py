"""Verify the native named signal-output connector-alias fault and control."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

RULE_ID = "connector.footprint_named_signal_output_open_outlier"


def verify_footprint_alias_named_signal_output(
    ctx: ConnectorReturnFixtureContext,
) -> dict[str, str]:
    """Bind native output-peer findings and coverage to both source fixtures."""
    receipts: dict[str, str] = {}
    for case, expected_status in (
        ("footprint-alias-named-signal-output-fault", "REVIEW"),
        ("footprint-alias-named-signal-output-control", "PASS"),
    ):
        report = ctx.reports[case, "first"]
        observed = ctx.observed_contracts[case, "first"]
        coverage = report.connector_peer_pin_coverage
        findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
        if (
            report.status != expected_status
            or coverage is None
            or coverage.netlist_sha256 != ctx.netlist_hashes[case, "first"]
            or observed.components["J1"].part_id is not None
            or observed.components["J2"].part_id is not None
            or observed.components["J1"].value != "Synthetic named signal-output peer"
            or observed.components["J2"].value != "Synthetic named signal-output peer"
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
                    ("1", "UART_TX", "output"),
                    ("2", "2", "passive"),
                )
            )
        ):
            raise ValueError(f"Native {case} lost complete PART_ID-free peer evidence")

        alias = coverage.footprint_alias_coverage
        net_pins = {net: set(pins) for net, pins in observed.nets.items()}
        if expected_status == "REVIEW":
            assigned_pins = {pin for pins in observed.nets.values() for pin in pins}
            unconnected_pins = {
                pin for pins in observed.unconnected_nets.values() for pin in pins
            }
            if (
                len(report.findings) != 1
                or len(findings) != 1
                or "J1.1" not in assigned_pins
                or "J2.1" in assigned_pins
                or "J2.1" not in unconnected_pins
                or net_pins.get("UART_TX") != {"J1.1"}
                or net_pins.get("COMMON_ANCHOR") != {"J1.2", "J2.2"}
                or findings[0].evidence.get("open_pins") != ("J2.1",)
                or findings[0].evidence.get("common_anchor_pin_numbers") != ("2",)
                or alias.status != "PARTIALLY_EVALUATED"
                or alias.candidate_group_count != 1
                or alias.eligible_peer_group_count != 1
                or alias.peer_scope_group_count != 1
                or alias.unassigned_assignment_pin_group_count != 1
                or alias.common_anchor_group_count != 1
                or alias.open_peer_pin_group_count != 1
                or alias.unanchored_open_peer_pin_group_count != 0
                or alias.open_outlier_finding_count != 1
            ):
                raise ValueError("Native named signal-output fault lost exact pin or coverage evidence")
        elif (
            report.findings
            or findings
            or alias.open_outlier_finding_count != 0
            or net_pins.get("UART_TX") != {"J1.1", "J2.1"}
            or net_pins.get("COMMON_ANCHOR") != {"J1.2", "J2.2"}
        ):
            raise ValueError("Native named signal-output control produced an open-peer finding")

        receipts[case] = json.dumps(
            coverage.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    return receipts
