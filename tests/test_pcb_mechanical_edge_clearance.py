"""Regression coverage for project-authored courtyard-to-edge DRC rules."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    NetlistContract,
    ProjectConfig,
    ProjectKind,
)
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_mechanical_edge_clearance import (
    mechanical_edge_rule_coverage_candidates,
    mechanical_edge_rule_coverage_issue,
)
from kicad_tooling.hwrepo.pcb_mechanical_edge_models import (
    PcbMechanicalEdgeClearanceMap,
    PcbMechanicalEdgeClearanceRequirement,
)

RULE_ID = "pcb.mechanical_edge_clearance_rule_coverage"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _requirement() -> PcbMechanicalEdgeClearanceRequirement:
    return PcbMechanicalEdgeClearanceRequirement(
        id="front-edge",
        basis="Reviewed connector-body clearance drawing",
        courtyard_layer="F.Courtyard",
        rule_name="front-mechanical-board-edge-clearance",
        minimum_clearance_nm=1_500_000,
    )


def _rule(
    *,
    layer: str = "F.Courtyard",
    condition: str = "B.Layer == 'Edge.Cuts'",
    minimum: str = "1.5mm",
    severity: str | None = None,
) -> str:
    severity_clause = "" if severity is None else f"(severity {severity})"
    return (
        "(version 1)\n"
        '(rule "front-mechanical-board-edge-clearance"\n'
        f'  (layer "{layer}")\n'
        f"  {severity_clause}\n"
        f"  (constraint physical_clearance (min {minimum}))\n"
        f'  (condition "{condition}"))'
    )


def test_project_authored_minimum_is_covered_by_exact_native_rule() -> None:
    constraints = native_constraints(_rule())

    assert len(constraints) == 1
    assert constraints[0].name == "physical_clearance"
    assert constraints[0].layer == "F.Courtyard"
    assert constraints[0].minimum_nm == 1_500_000
    assert (
        mechanical_edge_rule_coverage_issue(_requirement(), constraints, kicad_version="10.0.5")
        is None
    )


@pytest.mark.parametrize(
    ("source", "expected_issue"),
    (
        ("", "The named native DRC rule is missing."),
        (_rule(layer="B.Courtyard"), "The native rule does not target the exact"),
        (_rule(condition="B.Layer == 'Dwgs.User'"), "The native rule does not target the exact"),
        (_rule(minimum="1.4mm"), "The native physical-clearance bound differs"),
        (_rule(severity="ignore"), "The native DRC rule explicitly ignores"),
        (_rule(severity="warning"), "The native DRC rule severity is 'warning'"),
    ),
)
def test_wrong_or_suppressed_native_rule_is_incomplete(source: str, expected_issue: str) -> None:
    issue = mechanical_edge_rule_coverage_issue(_requirement(), native_constraints(source))

    assert issue is not None
    assert issue.startswith(expected_issue)


def test_duplicate_physical_clearance_constraints_are_ambiguous() -> None:
    source = _rule().replace(
        "(condition \"B.Layer == 'Edge.Cuts'\")",
        "(constraint physical_clearance (min 1.5mm))\n(condition \"B.Layer == 'Edge.Cuts'\")",
    )

    issue = mechanical_edge_rule_coverage_issue(_requirement(), native_constraints(source))

    assert issue == "The named native DRC rule has multiple physical_clearance constraints."


def test_competing_rule_for_exact_same_scope_keeps_coverage_incomplete() -> None:
    competing = _rule(minimum="0.5mm").replace(
        "front-mechanical-board-edge-clearance", "later-generic-courtyard-edge"
    )
    constraints = native_constraints(
        f"(version 1)\n{_rule().split(chr(10), 1)[1]}\n{competing.split(chr(10), 1)[1]}"
    )

    issue = mechanical_edge_rule_coverage_issue(_requirement(), constraints)

    assert (
        issue
        == "Other native rules target the same courtyard-edge scope: later-generic-courtyard-edge."
    )


def test_requirement_map_rejects_duplicate_side_or_rule_identity() -> None:
    front = _requirement()
    back = front.model_copy(
        update={
            "id": "back-edge",
            "courtyard_layer": "B.Courtyard",
            "rule_name": "back-mechanical-board-edge-clearance",
        }
    )

    assert PcbMechanicalEdgeClearanceMap(
        basis="Approved mechanical drawing", requirements=(front, back)
    )
    with pytest.raises(ValueError, match="one rule per courtyard side"):
        PcbMechanicalEdgeClearanceMap(
            basis="Approved mechanical drawing",
            requirements=(
                front,
                front.model_copy(
                    update={
                        "id": "front-edge-copy",
                        "rule_name": "front-mechanical-board-edge-clearance-copy",
                    }
                ),
            ),
        )


def test_rule_comparison_is_stable_under_native_rule_order() -> None:
    back = _rule(
        layer="B.Courtyard",
    ).replace("front-mechanical-board-edge-clearance", "back-mechanical-board-edge-clearance")
    front_body = _rule().split("\n", maxsplit=1)[1]
    back_body = back.split("\n", maxsplit=1)[1]
    source = f"(version 1)\n{front_body}\n{back_body}"
    reversed_source = f"(version 1)\n{back_body}\n{front_body}"

    first = native_constraints(source)
    second = native_constraints(reversed_source)

    assert mechanical_edge_rule_coverage_issue(_requirement(), first) == (
        mechanical_edge_rule_coverage_issue(_requirement(), second)
    )


def test_source_bound_scan_reports_missing_requirement_rule_and_policy_off(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import kicad_tooling.hwrepo.pcb_mechanical_edge_clearance as owner

    evidence = SimpleNamespace(
        rules_source=_rule(minimum="1.0mm"),
        rules_path="projects/synthetic/board.kicad_dru",
        rules_sha256="a" * 64,
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256="b" * 64,
        native_drc_path="build/native/drc.json",
        native_drc_sha256="c" * 64,
        native_summary_path="build/native/summary.json",
        native_summary_sha256="d" * 64,
    )
    monkeypatch.setattr(owner, "source_bound_drc_evidence", lambda *args: evidence)
    monkeypatch.setattr(owner, "verify_source_bound_drc_unchanged", lambda *args: None)
    config = cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.PCB, kicad_version="10.0.5"))
    policy = DesignLintPolicy(pcb_mechanical_edge_clearance_map=map_for_test())

    candidates = mechanical_edge_rule_coverage_candidates(
        tmp_path, config, policy, {}, tmp_path / "build/native"
    )

    assert len(candidates) == 1
    assert candidates[0].rule_id == RULE_ID
    assert candidates[0].evidence["expected_minimum_clearance_nm"] == ("1500000",)
    assert "confirmed, unambiguous source-bound native DRC coverage" in candidates[0].message

    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-mechanical-clearance",
        observed=NetlistContract(components={}, nets={}),
        netlist_sha256="e" * 64,
    )
    review = evaluate(
        coach.project_id,
        coach,
        DesignLintPolicy(pcb_mechanical_edge_clearance_map=map_for_test()),
        pcb_dru_rule_candidates=candidates,
    )
    review_finding = next(item for item in review.findings if item.rule_id == RULE_ID)
    assert review_finding.mode == "review"
    assert review_finding.disposition == "OPEN"

    blocked_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="Mechanical edge-rule coverage must be completed",
            ),
        ),
        pcb_mechanical_edge_clearance_map=map_for_test(),
    )
    blocked = evaluate(
        coach.project_id,
        coach,
        blocked_policy,
        pcb_dru_rule_candidates=candidates,
    )
    blocked_finding = next(item for item in blocked.findings if item.rule_id == RULE_ID)
    assert blocked_finding.mode == "block"
    assert blocked_finding.disposition == "OPEN"

    ignored_policy = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=review_finding.fingerprint,
                reason="Synthetic mechanical drawing reviewed the existing rule",
            ),
        ),
        pcb_mechanical_edge_clearance_map=map_for_test(),
    )
    ignored = evaluate(
        coach.project_id,
        coach,
        ignored_policy,
        pcb_dru_rule_candidates=candidates,
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"

    off_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="off",
                reason="Synthetic coverage prompt disabled for this project",
            ),
        ),
        pcb_mechanical_edge_clearance_map=map_for_test(),
    )
    assert (
        mechanical_edge_rule_coverage_candidates(
            tmp_path, config, off_policy, {}, tmp_path / "build/native"
        )
        == ()
    )


def map_for_test() -> PcbMechanicalEdgeClearanceMap:
    return PcbMechanicalEdgeClearanceMap(
        basis="Reviewed synthetic mechanical drawing",
        requirements=(_requirement(),),
    )
