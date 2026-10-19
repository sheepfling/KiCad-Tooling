"""Verify native, source-bound footprint-alias connector peer fixtures."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

RULE_ID = "connector.footprint_peer_pin_assignment_divergence"


def verify_footprint_alias_peer_assignments(
    ctx: ConnectorReturnFixtureContext,
) -> dict[str, str]:
    """Require the PART_ID-free fault and common-net control on native netlists."""
    receipts: dict[str, str] = {}
    for case, expected_status, expected_finding_count in (
        ("footprint-alias-fault", "REVIEW", 1),
        ("footprint-alias-control", "PASS", 0),
    ):
        report = ctx.reports[case, "first"]
        observed = ctx.observed_contracts[case, "first"]
        coverage = report.connector_peer_pin_coverage
        findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
        parts = tuple(observed.components[reference] for reference in ("J1", "J2"))
        if (
            report.status != expected_status
            or len(report.findings) != expected_finding_count
            or len(findings) != expected_finding_count
            or coverage is None
            or coverage.netlist_sha256 != ctx.netlist_hashes[case, "first"]
            or observed.components["J1"].part_id is not None
            or observed.components["J2"].part_id is not None
            or parts[0].value != parts[1].value
            or parts[0].footprint != parts[1].footprint
            or observed.component_symbols["J1"] == observed.component_symbols["J2"]
            or any(
                observed.pin_functions.get(f"{reference}.{number}") != f"Pin_{number}"
                or observed.pin_electrical_types.get(f"{reference}.{number}") != "passive"
                for reference in ("J1", "J2")
                for number in ("1", "2")
            )
        ):
            raise ValueError(f"Native {case} lost complete PART_ID-free alias evidence")

        alias = coverage.footprint_alias_coverage
        expected_alias_status = (
            "EVALUATED" if expected_finding_count else "NO_DIVERGENT_ASSIGNMENTS"
        )
        if (
            alias.status != expected_alias_status
            or alias.candidate_group_count != 1
            or alias.eligible_peer_group_count != 1
            or alias.peer_scope_group_count != 1
            or alias.evaluated_pin_group_count != 2
            or alias.compared_pin_group_count != 2
            or alias.common_assignment_pin_group_count != 2 - expected_finding_count
            or alias.generic_different_assignment_pin_group_count != expected_finding_count
            or alias.divergence_finding_count != expected_finding_count
        ):
            raise ValueError(f"Native {case} lost source-bound footprint-alias coverage counts")
        if expected_finding_count and findings[0].evidence.get("common_anchor_pin_numbers") != (
            "1",
        ):
            raise ValueError("Native footprint-alias fault lost its exact shared anchor")
        receipts[case] = json.dumps(
            coverage.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    return receipts
