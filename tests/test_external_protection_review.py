"""Synthetic regressions for external-protection applicability and review policy."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.external_protection import evaluate
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
