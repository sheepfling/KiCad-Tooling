"""Project lint must not return stale findings after source changes mid-run."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import design_lint_project_inspection
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_connectivity_snapshot_models import (
    DesignLintConnectivitySnapshot,
)
from kicad_tooling.hwrepo.design_lint_project_inspection import inspect_design_lint_summary
from kicad_tooling.hwrepo.models import DesignLintPolicy, NetlistContract
from tests.mcp_parity_support import parity_design_lint_policy
from tests.synthetic_design_lint_project import synthetic_design_lint_project

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint]


@pytest.mark.parametrize("change", ("edit", "add", "remove"))
def test_source_change_after_evaluation_blocks_project_inspection(
    tmp_path: Path, change: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path, parity_design_lint_policy(DesignLintPolicy())
    )
    source = root / "projects/controller/kicad/controller.kicad_sch"

    capture = design_lint_project_inspection.capture_connectivity_snapshot

    def capture_then_change(
        project_id: str,
        observed: NetlistContract,
        source_hashes: Mapping[str, str],
        netlist_sha256: str,
        kicad_version: str,
        toolchain_image: str,
    ) -> DesignLintConnectivitySnapshot:
        snapshot = capture(
            project_id, observed, source_hashes, netlist_sha256, kicad_version, toolchain_image
        )
        if change == "edit":
            source.write_text("changed while evaluating\n", encoding="utf-8")
        elif change == "add":
            (source.parent / "added.kicad_sch").write_text("new source\n", encoding="utf-8")
        else:
            source.unlink()
        return snapshot

    monkeypatch.setattr(
        design_lint_project_inspection, "capture_connectivity_snapshot", capture_then_change
    )
    report = inspect_design_lint_summary(root, "controller", native, evaluate)
    assert report.status == "BLOCKED"
    assert any(
        "Declared project source changed during design-lint inspection" in issue
        for issue in report.issues
    )
    assert report.connectivity_snapshot is None


def test_unchanged_source_keeps_project_inspection_available(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path, parity_design_lint_policy(DesignLintPolicy())
    )
    report = inspect_design_lint_summary(root, "controller", native, evaluate)
    assert report.status != "BLOCKED", report.issues
    assert report.connectivity_snapshot is not None
