"""Control-bias coverage must belong to the netlist being evaluated."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.control_input_bias import control_input_bias_heuristic_coverage
from kicad_tooling.hwrepo.control_input_models import ControlInputBiasHeuristicCoverage
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach, i2c_netlist
from tests.test_control_inputs import control_netlist, control_requirement

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_empty_complete_coverage_keeps_netlist_identity() -> None:
    observed = i2c_netlist(pullups=())
    coverage = control_input_bias_heuristic_coverage(
        observed,
        netlist_sha256="a" * 64,
        source_path="projects/synthetic/electrical.json",
        source_sha256="c" * 64,
        state="required",
        spec=control_requirement(bias_mode="internal"),
    )
    assert coverage.status == "COMPLETE"
    assert not coverage.entries
    assert coverage.netlist_sha256 == "a" * 64
    report = evaluate(
        "control-evidence",
        coach(observed),
        DesignLintPolicy(),
        control_input_bias_coverage=coverage,
    )
    assert report.status != "BLOCKED"


def test_unbound_or_stale_control_coverage_blocks_before_suppression() -> None:
    observed = control_netlist(fault="missing-resistor")
    coverage = control_input_bias_heuristic_coverage(
        observed,
        netlist_sha256="b" * 64,
        source_path="projects/synthetic/electrical.json",
        source_sha256="c" * 64,
        state="required",
        spec=control_requirement(bias_mode="internal"),
    )
    assert coverage.entries[0].status == "COVERED"
    legacy_empty = ControlInputBiasHeuristicCoverage.model_validate({"status": "COMPLETE"})
    for supplied in (coverage, legacy_empty):
        report = evaluate(
            "control-evidence",
            coach(observed),
            DesignLintPolicy(),
            control_input_bias_coverage=supplied,
        )
        assert report.status == "BLOCKED"
        assert report.control_input_bias_coverage.status == "BLOCKED"
        assert "different or unavailable native netlist hash" in report.issues[0]
        assert not report.findings


def test_blocked_coverage_keeps_its_reason_and_absent_coverage_stays_reviewable() -> None:
    observed = control_netlist(fault="missing-resistor")
    blocked = ControlInputBiasHeuristicCoverage(status="BLOCKED", issue="Contract unavailable")
    report = evaluate(
        "control-evidence", coach(observed), DesignLintPolicy(), control_input_bias_coverage=blocked
    )
    assert report.status == "BLOCKED"
    assert report.issues == ("Contract unavailable",)
    assert report.control_input_bias_coverage.issue == "Contract unavailable"

    without_coverage = evaluate("control-evidence", coach(observed), DesignLintPolicy())
    assert any(
        item.rule_id == "control.connected_control_input_without_visible_bias"
        for item in without_coverage.findings
    )


def test_covered_control_without_contract_identity_cannot_suppress_review() -> None:
    observed = control_netlist(fault="missing-resistor")
    coverage = control_input_bias_heuristic_coverage(
        observed,
        netlist_sha256="a" * 64,
        source_path=None,
        source_sha256=None,
        state="required",
        spec=control_requirement(bias_mode="internal"),
    )
    assert coverage.entries[0].status == "COVERED"
    report = evaluate(
        "control-evidence",
        coach(observed),
        DesignLintPolicy(),
        control_input_bias_coverage=coverage,
    )
    assert report.status == "BLOCKED"
    assert "identified electrical contract" in report.issues[0]


@pytest.mark.parametrize("state", ("NOT_CONFIGURED", "PENDING", "NOT_APPLICABLE"))
def test_unresolved_coverage_state_cannot_contain_a_covered_decision(state: str) -> None:
    observed = control_netlist(fault="missing-resistor")
    coverage = control_input_bias_heuristic_coverage(
        observed,
        netlist_sha256="a" * 64,
        source_path="projects/synthetic/electrical.json",
        source_sha256="b" * 64,
        state="required",
        spec=control_requirement(bias_mode="internal"),
    )
    contradictory = ControlInputBiasHeuristicCoverage.model_validate(
        {**coverage.model_dump(), "status": state}
    )
    report = evaluate(
        "control-evidence",
        coach(observed),
        DesignLintPolicy(),
        control_input_bias_coverage=contradictory,
    )
    assert report.status == "BLOCKED"
    assert "requires complete or open coverage" in report.issues[0]
