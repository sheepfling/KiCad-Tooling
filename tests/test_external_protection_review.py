"""Synthetic regressions for external-protection applicability and review policy."""

from __future__ import annotations

from typing import Literal

import pytest

from kicad_tooling.hwrepo.design_lint import candidates
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.external_protection import evaluate
from kicad_tooling.hwrepo.external_protection_models import (
    ExternalProtectionCoverageEntry,
    ExternalProtectionCoverageReport,
)
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.external_protection_support import (
    connector_coverage,
    observed_netlist,
    protection_lint_report,
    protection_map,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
]


@pytest.mark.parametrize(
    ("status", "entries"),
    (
        ("COMPLETE", ()),
        (
            "COMPLETE",
            (
                ExternalProtectionCoverageEntry(
                    connector_reference="J1", connector_pin="J1.1", status="UNDECLARED"
                ),
            ),
        ),
        (
            "INCOMPLETE",
            (
                ExternalProtectionCoverageEntry(
                    connector_reference="J1", connector_pin="J1.1", status="PROTECTED"
                ),
            ),
        ),
        ("UNDECLARED", ()),
    ),
)
@pytest.mark.evidence_lint
def test_external_protection_aggregate_status_must_match_coverage_rows(
    status: Literal["COMPLETE", "INCOMPLETE", "UNDECLARED"],
    entries: tuple[ExternalProtectionCoverageEntry, ...],
) -> None:
    with pytest.raises(ValueError, match="status must match its entries"):
        ExternalProtectionCoverageReport(
            status=status,
            netlist_sha256="f" * 64,
            entries=entries,
        )


@pytest.mark.evidence_lint
def test_not_requested_external_protection_cannot_contain_coverage_rows() -> None:
    entry = ExternalProtectionCoverageEntry(
        connector_reference="J1", connector_pin="J1.1", status="PROTECTED"
    )
    with pytest.raises(ValueError, match="Not-requested.*cannot contain entries"):
        ExternalProtectionCoverageReport(status="NOT_REQUESTED", entries=(entry,))


@pytest.mark.evidence_lint
def test_incomplete_and_undeclared_aggregate_states_accept_valid_mixed_rows() -> None:
    incomplete = ExternalProtectionCoverageReport(
        status="INCOMPLETE",
        netlist_sha256="f" * 64,
        entries=(
            ExternalProtectionCoverageEntry(
                connector_reference="J1", connector_pin="J1.1", status="INCOMPLETE"
            ),
            ExternalProtectionCoverageEntry(
                connector_reference="J2", connector_pin="J2.1", status="UNDECLARED"
            ),
        ),
    )
    undeclared = ExternalProtectionCoverageReport(
        status="UNDECLARED",
        netlist_sha256="f" * 64,
        entries=(
            ExternalProtectionCoverageEntry(
                connector_reference="J1", connector_pin="J1.1", status="UNDECLARED"
            ),
            ExternalProtectionCoverageEntry(
                connector_reference="J2", connector_pin="J2.1", status="PROTECTED"
            ),
        ),
    )

    assert tuple(entry.status for entry in incomplete.entries) == ("INCOMPLETE", "UNDECLARED")
    assert tuple(entry.status for entry in undeclared.entries) == ("UNDECLARED", "PROTECTED")


def test_missing_applicability_is_a_review_candidate_and_policy_can_block_it() -> None:
    observed = observed_netlist()
    coverage = evaluate(None, observed, connector_coverage(), "f" * 64)
    assert coverage.status == "UNDECLARED"
    assert coverage.entries[0].connector_pin == "J1.1"

    protection_findings = [
        item
        for item in candidates(observed, external_protection_coverage=coverage)
        if item.rule_id == "protection.unreviewed_interface_pin"
    ]
    assert len(protection_findings) == 1
    assert "does not assume protection is needed" in protection_findings[0].message

    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic",
        netlist_sha256="f" * 64,
        observed=observed,
    )
    review = evaluate_design_lint(
        "synthetic",
        coach,
        DesignLintPolicy(),
        external_protection_coverage=coverage,
    )
    assert review.status == "REVIEW"

    blocked = evaluate_design_lint(
        "synthetic",
        coach,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="protection.unreviewed_interface_pin",
                    mode="block",
                    reason="Synthetic project requires an applicability decision",
                ),
            )
        ),
        external_protection_coverage=coverage,
    )
    assert blocked.status == "FAIL"


@pytest.mark.evidence_lint
def test_stale_external_protection_coverage_blocks_before_its_rows_become_findings() -> None:
    observed = observed_netlist()
    stale = evaluate(None, observed, connector_coverage(), "b" * 64)
    assert stale.status == "UNDECLARED"
    assert stale.entries

    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic",
        netlist_sha256="a" * 64,
        observed=observed,
    )
    report = evaluate_design_lint(
        "synthetic",
        coach,
        DesignLintPolicy(),
        external_protection_coverage=stale,
    )

    assert report.status == "BLOCKED"
    assert report.external_protection_coverage.status == "BLOCKED"
    assert report.external_protection_coverage.netlist_sha256 == "b" * 64
    assert report.external_protection_coverage.entries == ()
    assert any("different or unavailable native netlist hash" in issue for issue in report.issues)
    assert not any(finding.rule_id.startswith("protection.") for finding in report.findings)


@pytest.mark.evidence_lint
def test_unavailable_netlist_keeps_the_external_protection_evidence_gap_visible() -> None:
    stale = evaluate(None, observed_netlist(), connector_coverage(), "b" * 64)
    coach = ContractCoachReport(
        status="BLOCKED",
        project_id="synthetic",
        issues=("Native netlist evidence is unavailable",),
    )

    report = evaluate_design_lint(
        "synthetic",
        coach,
        DesignLintPolicy(),
        external_protection_coverage=stale,
    )

    assert report.status == "BLOCKED"
    assert report.external_protection_coverage.status == "BLOCKED"
    assert report.external_protection_coverage.netlist_sha256 == "b" * 64
    assert any("different or unavailable native netlist hash" in issue for issue in report.issues)


@pytest.mark.evidence_lint
def test_missing_coach_report_retains_current_external_protection_coverage() -> None:
    digest = "f" * 64
    coverage = evaluate(None, observed_netlist(), connector_coverage(), digest)
    coach = ContractCoachReport(
        status="BLOCKED",
        project_id="synthetic",
        netlist_sha256=digest,
        issues=("A separate native-evidence check is unavailable",),
    )

    report = evaluate_design_lint(
        "synthetic",
        coach,
        DesignLintPolicy(),
        external_protection_coverage=coverage,
    )

    assert report.status == "BLOCKED"
    assert report.external_protection_coverage.status == "UNDECLARED"
    assert report.external_protection_coverage.entries == coverage.entries
    assert not any(finding.rule_id.startswith("protection.") for finding in report.findings)


@pytest.mark.evidence_lint
def test_blocked_external_protection_coverage_cannot_emit_candidates_from_retained_rows() -> None:
    observed = observed_netlist()
    coverage = evaluate(None, observed, connector_coverage(), "b" * 64).model_copy(
        update={"status": "BLOCKED", "issue": "stale source"}
    )

    assert not any(
        finding.rule_id.startswith("protection.")
        for finding in candidates(observed, external_protection_coverage=coverage)
    )


def test_unreviewed_protection_prompt_is_order_stable_and_authored_decision_clears_it() -> None:
    source = observed_netlist()
    source_sha256, original = protection_lint_report(None, source)
    rule_id = "protection.unreviewed_interface_pin"
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == rule_id
    }
    assert len(original_findings) == 1

    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered_sha256, reordered = protection_lint_report(None, reordered_source)
    assert source_sha256 != reordered_sha256
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == rule_id
    }
    assert reordered_findings == original_findings

    explicitly_not_required = protection_map(disposition="not_required")
    decided_sha256, decided = protection_lint_report(explicitly_not_required, source)
    assert decided_sha256 == source_sha256
    assert rule_id not in {item.rule_id for item in decided.findings}


def test_mapped_protection_mismatch_is_order_stable_and_native_repair_clears_it() -> None:
    requirements = protection_map()
    source = observed_netlist(fault="protector-wrong-net")
    source_sha256, original = protection_lint_report(requirements, source)
    rule_id = "protection.mapped_device_mismatch"
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == rule_id
    }
    assert len(original_findings) == 1

    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered_sha256, reordered = protection_lint_report(requirements, reordered_source)
    assert source_sha256 != reordered_sha256
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == rule_id
    }
    assert reordered_findings == original_findings

    repaired_sha256, repaired = protection_lint_report(requirements, observed_netlist())
    assert source_sha256 != repaired_sha256
    assert rule_id not in {item.rule_id for item in repaired.findings}
