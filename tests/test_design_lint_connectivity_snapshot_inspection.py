"""The source-bound snapshot path fails closed without a native netlist digest."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo import design_lint_project_inspection
from kicad_tooling.hwrepo.contract_coach import inspect_summary
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.slow]


def test_ready_inspection_without_netlist_digest_blocks_snapshot_capture(
    coach_workspace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach = inspect_summary(
        coach_workspace.root,
        coach_workspace.project_id,
        coach_workspace.native / "summary.json",
    )
    assert coach.status == "READY_FOR_REVIEW"
    assert coach.observed is not None

    monkeypatch.setattr(
        design_lint_project_inspection,
        "inspect_contract_summary",
        lambda *_args: coach.model_copy(update={"netlist_sha256": None}),
    )

    def unexpected_evaluation(*_args: object, **_kwargs: object) -> DesignLintReport:
        raise AssertionError("A missing netlist digest must block before lint evaluation")

    report = design_lint_project_inspection.inspect_design_lint_summary(
        coach_workspace.root,
        coach_workspace.project_id,
        coach_workspace.native / "summary.json",
        unexpected_evaluation,
    )

    assert report.status == "BLOCKED"
    assert report.connectivity_snapshot is None
    assert any("netlist hash is unavailable" in issue for issue in report.issues)
