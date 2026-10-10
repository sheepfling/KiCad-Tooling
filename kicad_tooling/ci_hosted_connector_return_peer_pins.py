"""Verify peer pin assignment, part identity, and coverage cases."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def verify_peer_pin_assignments(ctx: ConnectorReturnFixtureContext) -> dict[str, str]:
    """Verify peer pin assignment, part identity, and coverage cases."""
    peer_pin_coverage_receipts: dict[str, str] = {}
    for (
        case,
        expected_connector_count,
        expected_outlier_findings,
        expected_common_groups,
        expected_open_groups,
    ) in (
        ("peer-pin-outlier-fault", 3, 1, 1, 1),
        ("peer-pin-outlier-control", 3, 0, 2, 0),
        ("two-peer-open-fault", 2, 1, 1, 1),
        ("two-peer-no-connect-fault", 2, 1, 1, 1),
        ("two-peer-common-control", 2, 0, 2, 0),
    ):
        report = ctx.reports[case, "first"]
        coverage = report.connector_peer_pin_coverage
        if (
            coverage is None
            or coverage.status != "EVALUATED"
            or coverage.netlist_sha256 != ctx.netlist_hashes[case, "first"]
            or (coverage.connector_candidate_count != expected_connector_count)
            or (coverage.fitted_connector_count != expected_connector_count)
            or (coverage.exact_symbol_peer_group_count != 1)
            or (coverage.exact_symbol_pin_group_count != 2)
            or coverage.incomplete_pin_inventory_references
            or (
                coverage.exact_symbol_pin_groups_with_common_assignment_count
                != expected_common_groups
            )
            or (coverage.exact_symbol_pin_groups_with_open_assignment_count != expected_open_groups)
            or (coverage.peer_pin_outlier_finding_count != expected_outlier_findings)
        ):
            raise ValueError(f"Native {case} lost source-bound connector peer-pin coverage")
        peer_pin_coverage_receipts[case] = json.dumps(
            coverage.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    part_id_fault = ctx.reports["peer-pin-part-id-open-fault", "first"]
    part_id_fault_findings = {item.rule_id: item for item in part_id_fault.findings}
    if (
        part_id_fault.status != "REVIEW"
        or set(part_id_fault_findings) != {"connector.peer_pin_assignment_outlier"}
        or part_id_fault_findings["connector.peer_pin_assignment_outlier"].subject
        != "PART_ID SYNTHETIC-CONNECTOR-2PIN-001 pin 2"
        or (
            part_id_fault_findings["connector.peer_pin_assignment_outlier"].evidence.get(
                "peer_identity_basis"
            )
            != ("part_id",)
        )
        or (
            part_id_fault_findings["connector.peer_pin_assignment_outlier"].evidence.get(
                "outlier_pins"
            )
            != ("J2.2",)
        )
        or (
            ctx.observed_contracts["peer-pin-part-id-open-fault", "first"].nets
            != {"SYNTHETIC_DATA": ("J1.1", "J2.1"), "SYNTHETIC_RETURN": ("J1.2",)}
        )
    ):
        raise ValueError("Native PART_ID connector alias fault lost its exact open-pin evidence")
    part_id_control = ctx.reports["peer-pin-part-id-common-control", "first"]
    if part_id_control.status != "PASS" or part_id_control.findings:
        raise ValueError("Native PART_ID connector alias control no longer passes cleanly")
    part_id_split_fault = ctx.reports["peer-pin-part-id-split-fault", "first"]
    part_id_split_findings = {item.rule_id: item for item in part_id_split_fault.findings}
    part_id_split_observed = ctx.observed_contracts["peer-pin-part-id-split-fault", "first"]
    if (
        part_id_split_fault.status != "REVIEW"
        or set(part_id_split_findings) != {"connector.peer_pin_assignment_divergence"}
        or part_id_split_findings["connector.peer_pin_assignment_divergence"].subject
        != "PART_ID SYNTHETIC-CONNECTOR-2PIN-001 pin 2"
        or (
            dict(part_id_split_findings["connector.peer_pin_assignment_divergence"].evidence)
            != {
                "J1.2": ("SYNTHETIC_NET_2",),
                "J2.2": ("SYNTHETIC_NET_3",),
                "symbol": ("Synthetic:GenericPort", "Synthetic:GenericPortAlias"),
                "pin_number": ("2",),
                "missing_pin_function_pins": ("J1.2", "J2.2"),
                "peer_identity_basis": ("part_id",),
                "peer_identity": ("SYNTHETIC-CONNECTOR-2PIN-001",),
                "peer_symbols": ("Synthetic:GenericPort", "Synthetic:GenericPortAlias"),
            }
        )
        or (
            part_id_split_observed.nets
            != {
                "SYNTHETIC_NET_1": ("J1.1", "J2.1"),
                "SYNTHETIC_NET_2": ("J1.2",),
                "SYNTHETIC_NET_3": ("J2.2",),
            }
        )
    ):
        raise ValueError(
            f"Native PART_ID connector alias split fault lost exact divergence evidence: status={part_id_split_fault.status}, findings={[(item.rule_id, item.subject, dict(item.evidence)) for item in part_id_split_fault.findings]!r}, nets={part_id_split_observed.nets!r}"
        )
    for (
        case,
        expected_open,
        expected_different,
        expected_common,
        expected_outliers,
        expected_divergences,
    ) in (
        ("peer-pin-part-id-open-fault", 1, 1, 1, 1, 0),
        ("peer-pin-part-id-common-control", 0, 0, 2, 0, 0),
        ("peer-pin-part-id-split-fault", 0, 1, 1, 0, 1),
    ):
        report = ctx.reports[case, "first"]
        coverage = report.connector_peer_pin_coverage
        alias_coverage = None if coverage is None else coverage.part_id_alias_coverage
        if (
            coverage is None
            or alias_coverage is None
            or coverage.netlist_sha256 != ctx.netlist_hashes[case, "first"]
            or (coverage.exact_symbol_peer_group_count != 0)
            or (alias_coverage.status != "EVALUATED")
            or (alias_coverage.candidate_group_count != 1)
            or (alias_coverage.eligible_peer_group_count != 1)
            or (alias_coverage.compared_pin_group_count != 2)
            or (alias_coverage.common_assignment_pin_group_count != expected_common)
            or (alias_coverage.different_assignment_pin_group_count != expected_different)
            or (alias_coverage.open_assignment_pin_group_count != expected_open)
            or (alias_coverage.outlier_finding_count != expected_outliers)
            or (alias_coverage.divergence_finding_count != expected_divergences)
        ):
            raise ValueError(
                f"Native {case} lost source-bound PART_ID connector coverage: coverage={(None if coverage is None else coverage.model_dump(mode='json'))!r}; expected_open={expected_open}, expected_different={expected_different}, expected_outliers={expected_outliers}, expected_divergences={expected_divergences}, netlist_sha256={ctx.netlist_hashes[case, 'first']}"
            )
        peer_pin_coverage_receipts[case] = json.dumps(
            coverage.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    two_peer_fault = ctx.reports["two-peer-open-fault", "first"]
    two_peer_findings = {finding.rule_id: finding for finding in two_peer_fault.findings}
    if (
        two_peer_fault.status != "REVIEW"
        or set(two_peer_findings) != {"connector.peer_pin_assignment_outlier"}
        or dict(two_peer_findings["connector.peer_pin_assignment_outlier"].evidence)
        != {
            "J1.1": ("+5V",),
            "J2.1": (),
            "symbol": ("Lint:PeerPowerPort",),
            "pin_number": ("1",),
            "outlier_pins": ("J2.1",),
        }
        or (
            ctx.observed_contracts["two-peer-open-fault", "first"].nets
            != {"+5V": ("J1.1",), "GND": ("J1.2", "J2.2")}
        )
    ):
        raise ValueError("Two-peer open contact lost its exact native pin-assignment evidence")
    two_peer_no_connect_fault = ctx.reports["two-peer-no-connect-fault", "first"]
    no_connect_findings = {
        finding.rule_id: finding for finding in two_peer_no_connect_fault.findings
    }
    no_connect_observed = ctx.observed_contracts["two-peer-no-connect-fault", "first"]
    no_connect_pins = {
        pin for pins in no_connect_observed.unconnected_nets.values() for pin in pins
    }
    if (
        two_peer_no_connect_fault.status != "REVIEW"
        or set(no_connect_findings) != {"connector.peer_pin_assignment_outlier"}
        or dict(no_connect_findings["connector.peer_pin_assignment_outlier"].evidence)
        != {
            "J1.1": ("+5V",),
            "J2.1": (),
            "symbol": ("Lint:PeerPowerPort",),
            "pin_number": ("1",),
            "outlier_pins": ("J2.1",),
        }
        or (no_connect_observed.nets != {"+5V": ("J1.1",), "GND": ("J1.2", "J2.2")})
        or ("J2.1" not in no_connect_pins)
    ):
        raise ValueError(
            "Explicit no-connect peer contact must retain the REVIEW prompt and native pin evidence"
        )
    two_peer_control = ctx.reports["two-peer-common-control", "first"]
    if (
        two_peer_control.status != "PASS"
        or two_peer_control.findings
        or ctx.observed_contracts["two-peer-common-control", "first"].nets
        != {"+5V": ("J1.1", "J2.1"), "GND": ("J1.2", "J2.2")}
    ):
        raise ValueError("Two-peer common-net control no longer passes with exact native pins")
    return peer_pin_coverage_receipts
