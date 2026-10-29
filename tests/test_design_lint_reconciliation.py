"""Source-bound finding comparisons keep accepted and removed evidence visible."""

from __future__ import annotations

from typing import Literal

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from kicad_tooling.hwrepo.design_lint_connectivity_snapshot_models import (
    DesignLintConnectivitySnapshot,
    NetlistPinConnectivityState,
)
from kicad_tooling.hwrepo.design_lint_reconciliation import reconcile_design_lint_reports
from kicad_tooling.hwrepo.design_lint_reconciliation_text import reconciliation_text
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import DesignLintFinding

pytestmark = pytest.mark.design_lint


def _finding(
    fingerprint: str,
    *,
    disposition: Literal["OPEN", "IGNORED", "RULE_OFF"] = "OPEN",
    reason: str | None = None,
    message: str = "Repeated connector pin functions use different nets",
) -> DesignLintFinding:
    return DesignLintFinding(
        rule_id="connector.repeated_pin_function",
        fingerprint=fingerprint,
        subject="J1.7 / J2.7",
        message=message,
        evidence={"pins": ("J1.7", "J2.7"), "nets": ("RETURN_A", "RETURN_B")},
        mode="review" if disposition != "RULE_OFF" else "off",
        disposition=disposition,
        reason=reason,
    )


def _report(
    *,
    findings: tuple[DesignLintFinding, ...] = (),
    source_sha256: str = "a" * 64,
    netlist_sha256: str | None = "b" * 64,
    project_id: str = "synthetic-board",
    catalog: bool = True,
    status: Literal["PASS", "REVIEW", "FAIL", "BLOCKED"] = "REVIEW",
) -> DesignLintReport:
    sources = {"schematic.kicad_sch": source_sha256} if source_sha256 else {}
    snapshot = (
        DesignLintConnectivitySnapshot(
            project_id=project_id,
            source_hashes=sources,
            netlist_sha256=netlist_sha256,
            kicad_version="10.0.5",
            toolchain_image="registry.example/kicad@sha256:" + "c" * 64,
            coverage="COMPLETE",
            pin_states={
                "J1.7": NetlistPinConnectivityState(net="RETURN_A", peers=("J2.7",)),
                "J2.7": NetlistPinConnectivityState(net="RETURN_A", peers=("J1.7",)),
            },
        )
        if sources and netlist_sha256 is not None
        else None
    )
    return DesignLintReport(
        status=status,
        project_id=project_id,
        source_hashes=sources,
        netlist_sha256=netlist_sha256,
        connectivity_snapshot=snapshot,
        rule_catalog=rule_catalog() if catalog else None,
        findings=findings,
    )


def test_reconciliation_preserves_persistent_new_removed_and_reclassified_findings() -> None:
    persistent = _finding(
        "1" * 64,
        disposition="IGNORED",
        reason="Interface map documents isolation",
    )
    removed = _finding("2" * 64)
    reclassified_before = _finding("3" * 64)
    reclassified_after = _finding(
        "3" * 64,
        disposition="IGNORED",
        reason="Reviewed harness-only return",
    )
    added = _finding(
        "4" * 64,
        disposition="RULE_OFF",
        reason="Rule intentionally disabled for this project",
    )
    baseline = _report(findings=(removed, persistent, reclassified_before))
    current = _report(
        findings=(reclassified_after, added, persistent),
        source_sha256="c" * 64,
    )

    report = reconcile_design_lint_reports(baseline, current)

    assert report.status == "REVIEW"
    assert report.changed_source_paths == ("schematic.kicad_sch",)
    assert tuple(item.kind for item in report.transitions) == (
        "PERSISTING",
        "NO_LONGER_REPORTED",
        "RECLASSIFIED",
        "NEW",
    )
    assert report.transitions[0].current == persistent
    assert report.transitions[2].baseline == reclassified_before
    assert report.transitions[2].current == reclassified_after
    assert report.transitions[3].current == added
    assert report.transitions[1].baseline == removed


def test_unchanged_report_keeps_ignored_finding_visible() -> None:
    ignored = _finding("5" * 64, disposition="IGNORED", reason="Reviewed exact return topology")
    prior = _report(findings=(ignored,), status="PASS")

    report = reconcile_design_lint_reports(prior, prior)

    assert report.status == "UNCHANGED"
    assert len(report.transitions) == 1
    assert report.transitions[0].kind == "PERSISTING"
    assert report.transitions[0].current == ignored
    assert report.transitions[0].current is not None
    assert report.transitions[0].current.disposition == "IGNORED"
    assert report.transitions[0].current.reason == "Reviewed exact return topology"


def test_unchanged_open_finding_still_requires_review() -> None:
    finding = _finding("7" * 64)
    prior = _report(findings=(finding,), status="REVIEW")

    report = reconcile_design_lint_reports(prior, prior)

    assert report.status == "REVIEW"
    assert report.transitions[0].kind == "PERSISTING"
    assert report.current_findings == (finding,)
    assert any("does not accept" in item for item in report.context_changes)


@pytest.mark.parametrize(
    ("baseline", "current", "issue_fragment"),
    (
        (_report(source_sha256=""), _report(), "Baseline report has no source hashes"),
        (_report(netlist_sha256=None), _report(), "Baseline report has no native netlist hash"),
        (_report(catalog=False), _report(), "Baseline report has no rule catalog digest"),
        (
            _report(project_id="board-a"),
            _report(project_id="board-b"),
            "different project IDs",
        ),
    ),
)
def test_unbound_or_cross_project_comparison_blocks(
    baseline: DesignLintReport,
    current: DesignLintReport,
    issue_fragment: str,
) -> None:
    report = reconcile_design_lint_reports(baseline, current)

    assert report.status == "BLOCKED"
    assert report.issue is not None
    assert issue_fragment in report.issue


def test_duplicate_fingerprints_block_without_guessing_a_match() -> None:
    duplicate = _finding("6" * 64)
    baseline = _report(findings=(duplicate, duplicate))

    report = reconcile_design_lint_reports(baseline, _report())

    assert report.status == "BLOCKED"
    assert report.transitions == ()
    assert report.issue is not None
    assert "repeats finding fingerprints" in report.issue
    assert report.baseline_findings == (duplicate, duplicate)


def test_text_reconciliation_keeps_dismissed_and_removed_rows_reviewable() -> None:
    ignored = _finding("8" * 64, disposition="IGNORED", reason="Mapped in connector pinout")
    removed = _finding("9" * 64)
    report = reconcile_design_lint_reports(
        _report(findings=(ignored, removed)),
        _report(findings=(ignored,)),
    )

    rendered = reconciliation_text(report)

    assert report.status == "REVIEW"
    assert "PERSISTING" in rendered
    assert "IGNORED [connector.repeated_pin_function]" in rendered
    assert "Mapped in connector pinout" in rendered
    assert "NO_LONGER_REPORTED" in rendered
    assert "J1.7 / J2.7" in rendered


def test_changed_source_requires_review_when_findings_and_connectivity_match() -> None:
    result = reconcile_design_lint_reports(
        _report(status="PASS"), _report(status="PASS", source_sha256="d" * 64)
    )

    assert result.status == "REVIEW"
    assert result.changed_source_paths == ("schematic.kicad_sch",)
    assert result.transitions == ()
    assert result.connectivity_changes == ()
    assert "Declared source changed" in reconciliation_text(result)


def test_changed_native_netlist_requires_review_when_source_and_findings_match() -> None:
    result = reconcile_design_lint_reports(
        _report(status="PASS"), _report(status="PASS", netlist_sha256="e" * 64)
    )

    assert result.status == "REVIEW"
    assert result.changed_source_paths == ()
    assert result.transitions == ()
    assert result.connectivity_changes == ()
    assert "Native netlist digest changed" in reconciliation_text(result)
