"""Bind direct design-lint evaluation to the selected project identity."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.design_lint_component_coverage import ComponentMapCoverageInputs
from kicad_tooling.hwrepo.design_lint_evaluation_preparation import prepare_evaluation
from kicad_tooling.hwrepo.design_lint_evaluation_types import DesignLintEvaluationRequest
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]


def _request(
    *,
    project_id: str,
    coach_project_id: str,
    source_hashes: Mapping[str, str] | None = None,
    native_summary: str | None = None,
    netlist_sha256: str | None = "a" * 64,
) -> DesignLintEvaluationRequest:
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=coach_project_id,
        source_hashes=(
            {"kicad/main.kicad_sch": "b" * 64} if source_hashes is None else source_hashes
        ),
        observed=NetlistContract(components={}, nets={}),
        netlist_sha256=netlist_sha256,
        native_summary=native_summary,
    )
    return DesignLintEvaluationRequest(
        project_id=project_id,
        coach=coach,
        policy=DesignLintPolicy(),
        component_map_coverage=ComponentMapCoverageInputs(),
    )


@pytest.mark.parametrize(
    ("source_hashes", "native_summary"),
    [
        ({"kicad/main.kicad_sch": "b" * 64}, None),
        ({}, "build/native-summary.json"),
    ],
    ids=["source-hashes", "native-summary"],
)
def test_cross_project_coach_evidence_is_blocked_before_candidate_preparation(
    source_hashes: Mapping[str, str],
    native_summary: str | None,
) -> None:
    result = prepare_evaluation(
        _request(
            project_id="selected-project",
            coach_project_id="other-project",
            source_hashes=source_hashes,
            native_summary=native_summary,
        )
    )

    assert result.prepared is None
    assert result.report is not None
    assert result.report.status == "BLOCKED"
    assert result.report.project_id == "selected-project"
    assert result.report.netlist_sha256 is None
    assert result.report.source_hashes == {}
    expected_issue = (
        "Contract coach evidence belongs to project 'other-project', "
        "not requested project 'selected-project'"
    )
    assert result.report.issues == (expected_issue,)


def test_matching_coach_evidence_reaches_prepared_candidate_route() -> None:
    result = prepare_evaluation(
        _request(project_id="selected-project", coach_project_id="selected-project")
    )

    assert result.report is None
    assert result.prepared is not None
    assert result.prepared.candidate_inputs.observed is result.prepared.request.coach.observed
    assert result.prepared.candidate_inputs.catalog is result.prepared.catalog


def test_unbound_synthetic_coach_still_reaches_lower_level_preparation() -> None:
    result = prepare_evaluation(
        _request(
            project_id="selected-project",
            coach_project_id="synthetic-project",
            source_hashes={},
            netlist_sha256=None,
        )
    )

    assert result.report is None
    assert result.prepared is not None
