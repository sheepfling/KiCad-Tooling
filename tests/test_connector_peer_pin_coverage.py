"""Synthetic evidence coverage for repeated connector peer-pin heuristics."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_pins import connector_peer_pin_heuristic_coverage
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.design_lint import text_report
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    NetlistContract,
)

_REFERENCES = ("J1", "J2", "J3")
_NETLIST_SHA256 = "a" * 64


def peer_netlist(
    *,
    references: tuple[str, ...] = _REFERENCES,
    split_return: bool = False,
    open_generic_pin: bool = False,
    missing_inventory_reference: str | None = None,
    empty_inventory_reference: str | None = None,
    mismatched_inventory_reference: str | None = None,
    extra_assigned_pin: str | None = None,
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    return_nets = (
        {
            "RETURN_A": ("J1.2", "J2.2"),
            **({"RETURN_B": ("J3.2",)} if "J3" in references else {}),
        }
        if split_return
        else {"GND": tuple(f"{reference}.2" for reference in references)}
    )
    if open_generic_pin:
        return_nets = {"GND": tuple(f"{reference}.2" for reference in references[:-1])}
    inventories = {
        reference: ("1", "2")
        for reference in references
        if reference != missing_inventory_reference and reference != empty_inventory_reference
    }
    for reference in references:
        if reference == empty_inventory_reference:
            inventories[reference] = ()
        if reference == mismatched_inventory_reference:
            inventories[reference] = ("1",)
    if mismatched_inventory_reference is not None:
        return_nets = {
            "GND": tuple(
                f"{reference}.2"
                for reference in references
                if reference != mismatched_inventory_reference
            )
        }
    functions = {
        f"{reference}.{pin}": ("PWR" if pin == "1" else "GND" if split_return else f"Pin_{pin}")
        for reference in references
        for pin in ("1", "2")
        if not (reference == mismatched_inventory_reference and pin == "2")
    }
    return NetlistContract(
        components={},
        nets={
            "+5V": tuple(f"{reference}.1" for reference in references),
            **return_nets,
            **({"EXTRA": (extra_assigned_pin,)} if extra_assigned_pin is not None else {}),
        },
        dnp_components=dnp_references,
        component_symbols={reference: "Synthetic:TwoPinPort" for reference in references},
        pin_functions=functions,
        component_pin_numbers=inventories,
    )


def report_for(observed: NetlistContract) -> DesignLintReport:
    return evaluate_design_lint(
        "synthetic-connector-peers",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-connector-peers",
            observed=observed,
            netlist_sha256=_NETLIST_SHA256,
        ),
        DesignLintPolicy(),
    )


def test_common_peer_assignments_are_counted_without_a_finding() -> None:
    report = report_for(peer_netlist())
    coverage = report.connector_peer_pin_coverage

    assert coverage is not None
    assert coverage.status == "EVALUATED"
    assert coverage.netlist_sha256 == _NETLIST_SHA256
    assert coverage.connector_candidate_count == 3
    assert coverage.fitted_connector_count == 3
    assert coverage.exact_symbol_peer_group_count == 1
    assert coverage.exact_symbol_pin_group_count == 2
    assert coverage.exact_symbol_pin_groups_with_common_assignment_count == 2
    assert coverage.exact_symbol_pin_groups_with_different_assignments_count == 0
    assert coverage.peer_pin_outlier_finding_count == 0
    assert coverage.repeated_function_finding_count == 0
    assert "Connector peer-pin heuristic coverage: EVALUATED" in text_report(report)
    assert _NETLIST_SHA256 in text_report(report)


def test_split_meaningful_returns_are_reported_and_counted() -> None:
    report = report_for(peer_netlist(split_return=True))
    coverage = report.connector_peer_pin_coverage

    assert coverage is not None
    assert coverage.exact_symbol_pin_groups_with_common_assignment_count == 1
    assert coverage.exact_symbol_pin_groups_with_different_assignments_count == 1
    assert coverage.repeated_function_group_count == 2
    assert coverage.repeated_function_groups_with_common_assignment_count == 1
    assert coverage.repeated_function_groups_with_different_assignments_count == 1
    assert coverage.repeated_function_finding_count == 1
    findings = {item.rule_id for item in report.findings}
    assert "connector.repeated_pin_function" in findings
    assert "connector.peer_pin_assignment_outlier" not in findings


def test_open_generic_peer_pin_is_reported_with_a_valid_common_control() -> None:
    report = report_for(peer_netlist(open_generic_pin=True))
    coverage = report.connector_peer_pin_coverage

    assert coverage is not None
    assert coverage.exact_symbol_pin_groups_with_open_assignment_count == 1
    assert coverage.peer_pin_outlier_finding_count == 1
    assert "connector.peer_pin_assignment_outlier" in {item.rule_id for item in report.findings}


@pytest.mark.parametrize(
    ("observed", "expected_findings", "expected_common_groups"),
    (
        (peer_netlist(references=("J1", "J2"), open_generic_pin=True), 1, 1),
        (peer_netlist(references=("J1", "J2")), 0, 2),
    ),
    ids=("open-pin-fault", "common-assignment-control"),
)
def test_two_peer_open_pin_coverage_counts_fault_and_common_control(
    observed: NetlistContract, expected_findings: int, expected_common_groups: int
) -> None:
    report = report_for(observed)
    coverage = report.connector_peer_pin_coverage

    assert coverage is not None
    assert coverage.status == "EVALUATED"
    assert coverage.connector_candidate_count == 2
    assert coverage.fitted_connector_count == 2
    assert coverage.exact_symbol_peer_group_count == 1
    assert coverage.exact_symbol_pin_group_count == 2
    assert coverage.exact_symbol_pin_groups_with_common_assignment_count == expected_common_groups
    assert coverage.exact_symbol_pin_groups_with_open_assignment_count == (
        1 if expected_findings else 0
    )
    assert coverage.peer_pin_outlier_finding_count == expected_findings


@pytest.mark.parametrize(
    "observed",
    (
        peer_netlist(missing_inventory_reference="J3"),
        peer_netlist(empty_inventory_reference="J3"),
        peer_netlist(mismatched_inventory_reference="J3"),
        peer_netlist(extra_assigned_pin="J3.3"),
    ),
    ids=("missing", "empty", "mismatched", "extra-assigned-pin"),
)
def test_incomplete_inventory_is_visible_as_a_coverage_gap(observed: NetlistContract) -> None:
    coverage = connector_peer_pin_heuristic_coverage(
        observed,
        _NETLIST_SHA256,
        repeated_function_finding_count=0,
        peer_pin_outlier_finding_count=0,
        peer_pin_divergence_finding_count=0,
    )

    assert coverage.status == "INCOMPLETE_PIN_INVENTORY"
    assert coverage.incomplete_pin_inventory_references == ("J3",)
    report = report_for(observed)
    assert report.status == "REVIEW"
    assert "Incomplete exact-symbol pin inventory: J3" in text_report(report)


def test_all_dnp_candidates_have_a_distinct_no_fitted_status() -> None:
    coverage = connector_peer_pin_heuristic_coverage(
        peer_netlist(dnp_references=_REFERENCES),
        _NETLIST_SHA256,
        repeated_function_finding_count=0,
        peer_pin_outlier_finding_count=0,
        peer_pin_divergence_finding_count=0,
    )

    assert coverage.status == "NO_FITTED_CONNECTORS"
    assert coverage.connector_candidate_count == 3
    assert coverage.fitted_connector_count == 0
    assert coverage.exact_symbol_peer_group_count == 0
