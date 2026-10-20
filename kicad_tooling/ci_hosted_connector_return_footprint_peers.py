"""Verify native, source-bound footprint-alias connector peer fixtures."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext

RULE_ID = "connector.footprint_peer_pin_assignment_divergence"
OPEN_RULE_ID = "connector.footprint_peer_pin_open_outlier"
ALL_OPEN_RULE_ID = "connector.footprint_peer_pin_all_open"
NAMED_POWER_INPUT_OPEN_RULE_ID = "connector.footprint_named_power_input_open_outlier"


def verify_footprint_alias_peer_assignments(
    ctx: ConnectorReturnFixtureContext,
) -> dict[str, str]:
    """Validate Pin_N and numeric-label split faults and controls from native netlists."""
    receipts: dict[str, str] = {}
    for case, expected_status, expected_finding_count, expected_functions in (
        ("footprint-alias-fault", "REVIEW", 1, ("Pin_1", "Pin_2")),
        ("footprint-alias-control", "PASS", 0, ("Pin_1", "Pin_2")),
        ("footprint-alias-numeric-fault", "REVIEW", 1, ("1", "7")),
        ("footprint-alias-numeric-control", "PASS", 0, ("1", "7")),
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
                observed.pin_functions.get(f"{reference}.{number}")
                != expected_functions[int(number) - 1]
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
        if expected_finding_count and findings[0].evidence.get("pin_function") != (
            expected_functions[1],
        ):
            raise ValueError(f"Native {case} lost its generic pin-function evidence")
        receipts[case] = json.dumps(
            coverage.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    return receipts


def verify_footprint_alias_peer_open_outlier(
    ctx: ConnectorReturnFixtureContext,
) -> dict[str, str]:
    """Validate generic and named-power-input open faults and controls."""
    receipts: dict[str, str] = {}
    for case, expected_status, expected_finding_count, expected_functions in (
        ("footprint-alias-open-fault", "REVIEW", 1, ("Pin_1", "Pin_2")),
        ("footprint-alias-numeric-open-fault", "REVIEW", 1, ("1", "7")),
        ("footprint-alias-control", "PASS", 0, ("Pin_1", "Pin_2")),
    ):
        report = ctx.reports[case, "first"]
        observed = ctx.observed_contracts[case, "first"]
        coverage = report.connector_peer_pin_coverage
        findings = tuple(item for item in report.findings if item.rule_id == OPEN_RULE_ID)
        assigned_pins = {pin for pins in observed.nets.values() for pin in pins}
        unconnected_pins = {pin for pins in observed.unconnected_nets.values() for pin in pins}
        if (
            report.status != expected_status
            or len(report.findings) != expected_finding_count
            or len(findings) != expected_finding_count
            or coverage is None
            or coverage.netlist_sha256 != ctx.netlist_hashes[case, "first"]
            or observed.components["J1"].part_id is not None
            or observed.components["J2"].part_id is not None
            or observed.component_symbols["J1"] == observed.component_symbols["J2"]
            or any(
                observed.pin_functions.get(f"{reference}.{number}")
                != expected_functions[int(number) - 1]
                or observed.pin_electrical_types.get(f"{reference}.{number}") != "passive"
                for reference in ("J1", "J2")
                for number in ("1", "2")
            )
            or (
                case in {"footprint-alias-open-fault", "footprint-alias-numeric-open-fault"}
                and "J2.2" in assigned_pins
            )
            or (
                case in {"footprint-alias-open-fault", "footprint-alias-numeric-open-fault"}
                and "J2.2" not in unconnected_pins
            )
        ):
            raise ValueError(f"Native {case} lost expected PART_ID-free open-peer evidence")

        alias = coverage.footprint_alias_coverage
        if expected_finding_count:
            if (
                alias.status != "PARTIALLY_EVALUATED"
                or alias.candidate_group_count != 1
                or alias.eligible_peer_group_count != 1
                or alias.peer_scope_group_count != 1
                or alias.unassigned_assignment_pin_group_count != 1
                or alias.common_anchor_group_count != 1
                or alias.open_peer_pin_group_count != 1
                or alias.unanchored_open_peer_pin_group_count != 0
                or alias.open_outlier_finding_count != 1
                or findings[0].evidence.get("open_pins") != ("J2.2",)
                or findings[0].evidence.get("common_anchor_pin_numbers") != ("1",)
                or findings[0].evidence.get("pin_function") != (expected_functions[1],)
            ):
                raise ValueError("Native footprint-alias open fault lost its exact peer evidence")
        elif alias.open_outlier_finding_count != 0:
            raise ValueError("Native footprint-alias common control produced an open-peer prompt")

        receipts[case] = json.dumps(
            coverage.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    case = "footprint-alias-named-power-input-fault"
    report = ctx.reports[case, "first"]
    observed = ctx.observed_contracts[case, "first"]
    coverage = report.connector_peer_pin_coverage
    findings = tuple(
        item for item in report.findings if item.rule_id == NAMED_POWER_INPUT_OPEN_RULE_ID
    )
    if (
        report.status != "REVIEW"
        or len(report.findings) != 1
        or len(findings) != 1
        or coverage is None
        or coverage.netlist_sha256 != ctx.netlist_hashes[case, "first"]
        or observed.components["J1"].part_id is not None
        or observed.components["J2"].part_id is not None
        or observed.component_symbols["J1"] == observed.component_symbols["J2"]
        or any(
            observed.pin_functions.get(f"{reference}.{number}") != function
            or observed.pin_electrical_types.get(f"{reference}.{number}") != pin_type
            for reference in ("J1", "J2")
            for number, function, pin_type in (
                ("1", "BIAS_IN", "power_in"),
                ("2", "2", "passive"),
            )
        )
        or findings[0].evidence.get("open_pins") != ("J2.1",)
        or findings[0].evidence.get("common_anchor_pin_numbers") != ("2",)
    ):
        raise ValueError("Native named power-input fault lost exact PART_ID-free peer evidence")
    alias = coverage.footprint_alias_coverage
    if (
        alias.status != "PARTIALLY_EVALUATED"
        or alias.candidate_group_count != 1
        or alias.eligible_peer_group_count != 1
        or alias.peer_scope_group_count != 1
        or alias.unassigned_assignment_pin_group_count != 1
        or alias.common_anchor_group_count != 1
        or alias.open_peer_pin_group_count != 1
        or alias.unanchored_open_peer_pin_group_count != 0
        or alias.open_outlier_finding_count != 1
    ):
        raise ValueError("Native named power-input fault lost its exact coverage counts")
    receipts[case] = json.dumps(
        coverage.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    case = "footprint-alias-named-power-input-control"
    report = ctx.reports[case, "first"]
    coverage = report.connector_peer_pin_coverage
    if (
        report.status != "PASS"
        or report.findings
        or coverage is None
        or coverage.netlist_sha256 != ctx.netlist_hashes[case, "first"]
        or coverage.footprint_alias_coverage.open_outlier_finding_count != 0
    ):
        raise ValueError("Native named power-input common control produced an open-peer finding")
    receipts[case] = json.dumps(
        coverage.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return receipts


def verify_footprint_alias_peer_all_open(
    ctx: ConnectorReturnFixtureContext,
) -> dict[str, str]:
    """Validate the all-open generic alias fault against an assigned control."""
    receipts: dict[str, str] = {}
    cases = (
        ("footprint-alias-all-open-fault", "REVIEW", 1),
        ("footprint-alias-control", "PASS", 0),
    )
    for case, expected_status, expected_count in cases:
        report = ctx.reports[case, "first"]
        observed = ctx.observed_contracts[case, "first"]
        coverage = report.connector_peer_pin_coverage
        findings = tuple(item for item in report.findings if item.rule_id == ALL_OPEN_RULE_ID)
        assigned = {pin for pins in observed.nets.values() for pin in pins}
        if (
            report.status != expected_status
            or len(findings) != expected_count
            or coverage is None
            or coverage.netlist_sha256 != ctx.netlist_hashes[case, "first"]
            or observed.components["J1"].part_id is not None
            or observed.components["J2"].part_id is not None
            or observed.component_symbols["J1"] == observed.component_symbols["J2"]
            or any(
                observed.pin_functions.get(f"{reference}.{number}") != function
                or observed.pin_electrical_types.get(f"{reference}.{number}") != "passive"
                for reference in ("J1", "J2")
                for number, function in (("1", "Pin_1"), ("2", "Pin_2"))
            )
        ):
            raise ValueError(f"Native {case} lost its PART_ID-free all-open alias evidence")

        alias = coverage.footprint_alias_coverage
        if expected_count:
            if (
                not {"2"} <= set(observed.component_pin_numbers.get("J1", ()))
                or not {"2"} <= set(observed.component_pin_numbers.get("J2", ()))
                or {"J1.2", "J2.2"} & assigned
                or alias.candidate_group_count != 1
                or alias.eligible_peer_group_count != 1
                or alias.peer_scope_group_count != 1
                or alias.unassigned_assignment_pin_group_count != 1
                or alias.common_anchor_group_count != 1
                or alias.all_open_peer_pin_group_count != 1
                or alias.unanchored_all_open_peer_pin_group_count != 0
                or alias.all_open_finding_count != 1
                or findings[0].evidence.get("open_pins") != ("J1.2", "J2.2")
                or findings[0].evidence.get("common_anchor_pin_numbers") != ("1",)
            ):
                raise ValueError("Native all-open footprint-alias fault lost exact pin evidence")
        elif alias.all_open_finding_count != 0:
            raise ValueError("Native assigned control produced an all-open alias finding")

        receipts[case] = json.dumps(
            coverage.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    return receipts
