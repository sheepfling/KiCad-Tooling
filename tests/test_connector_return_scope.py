"""Source-matched project scopes for connector return-pin heuristics."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.connector_coverage import (
    evaluate as evaluate_connector_coverage,
)
from kicad_tooling.hwrepo.connector_coverage import (
    source_matched_connector_return_comparison_groups,
)
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.design_lint import text_report
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
)
from tests.design_lint_fixtures.connector_coverage import (
    interface_record,
    inventory_review,
)
from tests.design_lint_fixtures.connector_mixed_return import (
    two_usb_one_serial_return_case,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
    pytest.mark.design_lint_rule(rule_id="connector.repeated_pin_function"),
]


def _lint(netlist: NetlistContract, coverage):
    return evaluate_design_lint(
        "synthetic-return-comparison-scope",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-return-comparison-scope",
            observed=netlist,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )


def _return_findings(report):
    return tuple(
        finding
        for finding in report.findings
        if finding.rule_id == "connector.repeated_pin_function"
        and finding.subject.endswith("ground/return")
    )


def test_split_returns_in_one_reviewed_group_still_need_review() -> None:
    groups = {reference: "external-returns" for reference in ("J1", "J2", "J3")}
    netlist, coverage = two_usb_one_serial_return_case(
        common_return=False, return_comparison_groups=groups
    )

    assert source_matched_connector_return_comparison_groups(netlist, coverage) == {
        reference: (
            "external-returns",
            f"Reviewed {reference} in return-comparison group external-returns",
        )
        for reference in ("J1", "J2", "J3")
    }
    report = _lint(netlist, coverage)
    findings = _return_findings(report)
    assert len(findings) == 1
    finding = findings[0]
    assert {"J1.3", "J2.3", "J3.3"} <= set(finding.evidence)
    assert finding.evidence["return_comparison_group"] == ("external-returns",)
    assert len(finding.evidence["return_comparison_basis"]) == 3
    assert "return-comparison group external-returns" in finding.message
    assert "does not establish continuity, bonding, or electrical isolation" in finding.message
    rendered = text_report(report)
    assert "Return-comparison group: external-returns" in rendered
    assert "Return-comparison basis: Reviewed J1" in rendered


def test_distinct_reviewed_return_groups_suppress_only_cross_group_prompt() -> None:
    netlist, coverage = two_usb_one_serial_return_case(
        common_return=False,
        return_comparison_groups={"J1": "host-returns", "J2": "host-returns", "J3": "usb2-return"},
    )

    assert source_matched_connector_return_comparison_groups(netlist, coverage).keys() == {
        "J1",
        "J2",
        "J3",
    }
    assert not _return_findings(_lint(netlist, coverage))


def test_common_returns_in_one_reviewed_group_are_quiet() -> None:
    netlist, coverage = two_usb_one_serial_return_case(
        common_return=True,
        return_comparison_groups={
            reference: "external-returns" for reference in ("J1", "J2", "J3")
        },
    )

    assert not _return_findings(_lint(netlist, coverage))


def test_missing_or_stale_group_evidence_restores_global_comparison() -> None:
    netlist, missing_coverage = two_usb_one_serial_return_case(
        common_return=False,
        return_comparison_groups={"J1": "external-returns", "J2": "external-returns"},
    )
    assert source_matched_connector_return_comparison_groups(netlist, missing_coverage) == {
        "J1": (
            "external-returns",
            "Reviewed J1 in return-comparison group external-returns",
        ),
        "J2": (
            "external-returns",
            "Reviewed J2 in return-comparison group external-returns",
        ),
    }
    missing_finding = _return_findings(_lint(netlist, missing_coverage))[0]
    assert {"J1.3", "J2.3", "J3.3"} <= set(missing_finding.evidence)
    assert "return_comparison_group" not in missing_finding.evidence

    scoped = {reference: "external-returns" for reference in ("J1", "J2", "J3")}
    split, stale_coverage = two_usb_one_serial_return_case(
        common_return=False, return_comparison_groups=scoped
    )
    changed_nets = dict(split.nets)
    del changed_nets["USB2_D+"]
    changed_nets["USB2_D+_REVISED"] = ("J3.1",)
    changed = split.model_copy(update={"nets": changed_nets})
    assert "J3" not in source_matched_connector_return_comparison_groups(changed, stale_coverage)
    stale_finding = _return_findings(_lint(changed, stale_coverage))[0]
    assert {"J1.3", "J2.3", "J3.3"} <= set(stale_finding.evidence)
    assert "return_comparison_group" not in stale_finding.evidence


def test_return_group_without_mapped_return_role_makes_coverage_incomplete() -> None:
    observed = NetlistContract(
        components={},
        nets={"TX": ("J1.1",), "RX": ("J1.2",)},
        component_symbols={"J1": "Synthetic:DebugConnector"},
        component_pin_numbers={"J1": ("1", "2")},
    )
    review = ConnectorInterfaceReview(
        reference="J1",
        disposition="interface",
        basis="Synthetic reviewed signal-only interface",
        interface_id="debug-port",
        pin_map={"1": "1", "2": "2"},
        return_comparison_group="debug-return",
        return_comparison_basis="Synthetic return comparison scope",
    )
    coverage = evaluate_connector_coverage(
        observed,
        ("debug-port",),
        (review,),
        interfaces={"debug-port": interface_record()},
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="b" * 64,
        inventory_review=inventory_review(),
    )
    entry = coverage.entries[0]
    assert entry.status == "INCOMPLETE"
    assert "has no return-role pin" in entry.issues[0]
    assert source_matched_connector_return_comparison_groups(observed, coverage) == {}

    with pytest.raises(ValidationError):
        ConnectorInterfaceReview.model_validate(
            review.model_dump(exclude={"return_comparison_basis"})
        )
