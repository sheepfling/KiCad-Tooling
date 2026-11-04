"""Keep complete design-lint findings consistent with mapped coverage rows."""

from __future__ import annotations

from typing import Literal

import pytest

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from tests.design_lint_evidence_fixtures import (
    crystal_coverage,
    external_protection_coverage,
    rc_filter_coverage,
    regulator_coverage,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint]

_REPORT_NETLIST_HASH = "a" * 64


def test_external_protection_rows_reconcile_with_a_complete_finding_list() -> None:
    coverage = external_protection_coverage("UNDECLARED", _REPORT_NETLIST_HASH)
    report_data = {
        "status": "REVIEW",
        "project_id": "synthetic-source-evidence",
        "netlist_sha256": _REPORT_NETLIST_HASH,
        "external_protection_coverage": coverage,
    }

    with pytest.raises(ValueError, match="findings must match source-bound coverage rows"):
        DesignLintReport.model_validate(report_data)

    finding = DesignLintFinding(
        rule_id="protection.unreviewed_interface_pin",
        fingerprint="d" * 64,
        subject="J1.1: synthetic interface",
        message="A protection applicability decision is needed.",
        evidence={"connector": ("J1",)},
        mode="review",
        disposition="OPEN",
    )
    report = DesignLintReport.model_validate({**report_data, "findings": (finding,)})
    assert report.findings == (finding,)


def test_external_protection_mismatch_rows_reconcile_with_a_complete_finding_list() -> None:
    report_data = {
        "status": "REVIEW",
        "project_id": "synthetic-source-evidence",
        "netlist_sha256": _REPORT_NETLIST_HASH,
        "external_protection_coverage": external_protection_coverage(
            "INCOMPLETE", _REPORT_NETLIST_HASH
        ),
    }

    with pytest.raises(ValueError, match="findings must match source-bound coverage rows"):
        DesignLintReport.model_validate(report_data)

    finding = DesignLintFinding(
        rule_id="protection.mapped_device_mismatch",
        fingerprint="f" * 64,
        subject="J1.1: mapped protection requirement",
        message="The synthetic mapped protection evidence differs from its expected pin map.",
        evidence={"connector": ("J1",)},
        mode="review",
        disposition="OPEN",
    )
    report = DesignLintReport.model_validate({**report_data, "findings": (finding,)})
    assert report.findings == (finding,)


@pytest.mark.parametrize(
    ("field_name", "coverage", "rule_id"),
    (
        (
            "crystal_network_coverage",
            crystal_coverage(_REPORT_NETLIST_HASH),
            "oscillator.crystal_load_network_mismatch",
        ),
        (
            "regulator_feedback_coverage",
            regulator_coverage(_REPORT_NETLIST_HASH),
            "power.regulator_feedback_mismatch",
        ),
        (
            "rc_filter_coverage",
            rc_filter_coverage(_REPORT_NETLIST_HASH),
            "filter.rc_corner_mismatch",
        ),
    ),
)
def test_component_analysis_rows_reconcile_with_complete_findings(
    field_name: str,
    coverage: object,
    rule_id: Literal[
        "oscillator.crystal_load_network_mismatch",
        "power.regulator_feedback_mismatch",
        "filter.rc_corner_mismatch",
    ],
) -> None:
    report_data = {
        "status": "REVIEW",
        "project_id": "synthetic-source-evidence",
        "netlist_sha256": _REPORT_NETLIST_HASH,
        field_name: coverage,
    }
    with pytest.raises(ValueError, match="findings must match source-bound coverage rows"):
        DesignLintReport.model_validate(report_data)

    finding = DesignLintFinding(
        rule_id=rule_id,
        fingerprint="e" * 64,
        subject="Synthetic mapped component mismatch",
        message="A mapped component comparison needs review.",
        evidence={"component": ("U1",)},
        mode="review",
        disposition="OPEN",
    )
    report = DesignLintReport.model_validate({**report_data, "findings": (finding,)})
    assert report.findings == (finding,)

    blocked_report = DesignLintReport.model_validate(
        {
            **report_data,
            "status": "BLOCKED",
            "issues": ("Another evidence route is unavailable",),
        }
    )
    assert blocked_report.findings == ()


def test_blocked_report_can_retain_coverage_without_a_complete_finding_list() -> None:
    report = DesignLintReport.model_validate(
        {
            "status": "BLOCKED",
            "project_id": "synthetic-source-evidence",
            "netlist_sha256": _REPORT_NETLIST_HASH,
            "external_protection_coverage": external_protection_coverage(
                "UNDECLARED", _REPORT_NETLIST_HASH
            ),
        }
    )

    assert report.external_protection_coverage.entries[0].status == "UNDECLARED"
