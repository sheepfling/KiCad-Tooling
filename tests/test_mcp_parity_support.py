"""Semantic comparison rules for source-bound CLI/MCP parity tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.models import DesignLintReport
from tests.mcp_parity_support import (
    McpParityHarness,
    normalize_per_run_pcb_geometry_paths,
    run_mcp_parity,
    semantic_design_lint_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.parity_lint]


def test_async_parity_runner_cleans_up_temporary_workspace(tmp_path: Path) -> None:
    captured: dict[str, Path] = {}

    class ProbeCase(McpParityHarness):
        def setUp(self) -> None:
            self.temporary = tempfile.TemporaryDirectory(dir=tmp_path)

        async def exercise(self) -> None:
            self.assertEqual(2 + 2, 4)
            with self.subTest(value="synthetic"):
                self.assertTrue(True)
            captured["workspace"] = Path(self.temporary.name)

    run_mcp_parity(ProbeCase, "exercise")

    assert not captured["workspace"].exists()


def test_design_lint_semantics_ignore_only_per_run_geometry_directory() -> None:
    cli = DesignLintReport(
        status="REVIEW",
        project_id="synthetic",
        issues=("inspect build/design-lint/pcb-geometry-a3e29f43021d/snapshot.json",),
    )
    mcp = DesignLintReport(
        status="REVIEW",
        project_id="synthetic",
        issues=("inspect build/design-lint/pcb-geometry-0f89436b9a42/snapshot.json",),
    )

    assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
    assert semantic_design_lint_report(cli) != semantic_design_lint_report(
        mcp.model_copy(update={"status": "PASS"})
    )
    assert normalize_per_run_pcb_geometry_paths(
        {"receipt": "build/design-lint/pcb-geometry-0f89436b9a42/native.command.json"}
    ) == {"receipt": "build/design-lint/pcb-geometry-<run>/native.command.json"}
