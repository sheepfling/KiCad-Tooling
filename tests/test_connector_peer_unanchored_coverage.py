"""Review unanchored connector-alias splits without complete project coverage."""

from __future__ import annotations

from typing import Literal

import pytest

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
)
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.connector_footprint_peer_support import peer_netlist
from tests.connector_peer_unanchored_scope_support import lint_report, reviewed_coverage

RULE_ID = "connector.footprint_peer_unanchored_scope_coverage_missing"
SCOPE_RULE_ID = "connector.footprint_peer_unanchored_scope_unreviewed"

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("coverage_kind", ("not-supplied", "undeclared", "incomplete-pin-maps"))
def test_unanchored_alias_split_prompts_when_coverage_is_missing(
    coverage_kind: str,
) -> None:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    if coverage_kind == "not-supplied":
        coverage = None
    elif coverage_kind == "undeclared":
        coverage = evaluate_connector_coverage(observed, (), (), interfaces={})
    else:
        coverage = reviewed_coverage(observed, (None, None), pin_maps_complete=False)

    report = lint_report(observed, coverage)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert len(findings) == 1
    finding = findings[0]
    assert report.status == "REVIEW"
    assert finding.mode == "review"
    assert finding.evidence["references"] == ("J1", "J2")
    assert finding.evidence["unanchored_generic_pin_numbers"] == ("1", "2")
    assert finding.evidence["pin_assignments"] == (
        "pin 1: J1.1=PORT_A; J2.1=PORT_B",
        "pin 2: J1.2=DATA_A; J2.2=DATA_B",
    )
    expected_status = (
        "NOT_SUPPLIED"
        if coverage is None
        else "UNDECLARED"
        if coverage_kind == "undeclared"
        else "INCOMPLETE"
    )
    assert finding.evidence["coverage_status"] == (expected_status,)
    assert "require any contacts to be joined" in finding.message
    assert report.connector_peer_pin_coverage is not None
    assert (
        report.connector_peer_pin_coverage.footprint_alias_coverage.uncovered_peer_assignment_scope_finding_count
        == 1
    )
    assert not any(
        item.rule_id
        in {SCOPE_RULE_ID, "connector.footprint_peer_pin_unanchored_assignment_divergence"}
        for item in report.findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_complete_peer_map_is_handled_by_scope_prompt_and_not_coverage_prompt() -> None:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    report = lint_report(observed, reviewed_coverage(observed, (None, None)))

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    assert any(item.rule_id == SCOPE_RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_assignments_and_explicit_not_applicable_review_are_valid_controls() -> None:
    common = peer_netlist(assignments=(("COMMON", "COMMON"), ("DATA", "DATA")))
    assert not any(item.rule_id == RULE_ID for item in lint_report(common).findings)

    split = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    not_applicable = evaluate_connector_coverage(
        split,
        (),
        tuple(
            ConnectorInterfaceReview(
                reference=reference,
                disposition="not_applicable",
                basis="Synthetic review confirms this connector is outside the interface scope",
            )
            for reference in ("J1", "J2")
        ),
        interfaces={},
        inventory_review=ConnectorInventoryReview(
            basis="Synthetic connector inventory was reviewed"
        ),
    )

    assert not_applicable.status == "COMPLETE"
    assert not any(item.rule_id == RULE_ID for item in lint_report(split, not_applicable).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_connector_alias_suppresses_the_uncovered_scope_prompt() -> None:
    split = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    stale_coverage = ConnectorCoverageReport(
        status="INCOMPLETE",
        scope="Synthetic connector coverage state",
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="STALE",
                issues=("Synthetic map no longer matches this source",),
            ),
            ConnectorCoverageEntry(reference="J2", status="UNDECLARED"),
        ),
    )

    assert not any(item.rule_id == RULE_ID for item in lint_report(split, stale_coverage).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("mode", "disposition", "report_status"),
    (
        ("review", "OPEN", "REVIEW"),
        ("block", "OPEN", "FAIL"),
        ("off", "RULE_OFF", "PASS"),
    ),
)
def test_coverage_prompt_obeys_project_policy(
    mode: Literal["review", "block", "off"], disposition: str, report_status: str
) -> None:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Synthetic test of project-owned lint policy",
            ),
        )
    )

    report = lint_report(observed, policy=policy)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.mode == mode
    assert finding.disposition == disposition
    assert report.status == report_status


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_coverage_prompt_exact_ignore_matches_only_its_fingerprint() -> None:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    initial = lint_report(observed)
    finding = next(item for item in initial.findings if item.rule_id == RULE_ID)
    policy = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic exact exception for a deliberately separate connector group",
            ),
        )
    )

    report = lint_report(observed, policy=policy)
    matches = [item for item in report.findings if item.rule_id == RULE_ID]
    assert len(matches) == 1
    assert matches[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_coverage_prompt_fingerprint_is_stable_under_native_mapping_reordering() -> None:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )
    left = lint_report(observed)
    right = lint_report(reordered)
    left_findings = tuple(item for item in left.findings if item.rule_id == RULE_ID)
    right_findings = tuple(item for item in right.findings if item.rule_id == RULE_ID)

    assert tuple((item.fingerprint, item.evidence) for item in left_findings) == tuple(
        (item.fingerprint, item.evidence) for item in right_findings
    )
