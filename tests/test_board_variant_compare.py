"""Comparison of two saved native board populations and CLI/MCP parity."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.board_variant_compare import compare_board_variants
from kicad_tooling.hwrepo.board_variant_compare_models import BoardVariantComparisonReport
from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity
from tests.test_cross_probe_variant import _inputs

pytestmark = pytest.mark.template_checkout


def test_named_board_variants_compare_references_and_fitted_quantities(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    _, findings, _ = _inputs(root, island)
    report = compare_board_variants(
        root,
        "controller",
        findings,
        "STANDARD",
        "ALT",
        Path("build/board-variant-comparison/review"),
    )
    assert report.before.name == "STANDARD" and report.after.name == "ALT"
    rows = {item.reference: item for item in report.references}
    assert rows["R1"].change == "CHANGED"
    assert rows["R1"].before and rows["R1"].after
    assert rows["R1"].before.board == "FITTED" and rows["R1"].after.board == "DNP"
    assert rows["R2"].before and rows["R2"].after
    assert rows["R2"].before.schematic == "DNP"
    assert rows["R2"].after.part_id == "resistor-alt"
    assert rows["J9"].change == "UNCHANGED"
    assert report.before.unresolved_fitted == report.after.unresolved_fitted == ("J9",)
    assert {(item.part_id, item.change, item.before, item.after) for item in report.quantities} == {
        ("resistor-1k", "REMOVED", 1, 0),
        ("resistor-alt", "ADDED", 0, 1),
    }
    output = Path(report.output_directory)
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "STANDARD → ALT" in html and "Unresolved fitted references" in html
    assert read_model(output / "comparison.json", BoardVariantComparisonReport) == report
    assert digest(output / "index.html") == report.artifacts_sha256["index.html"]


def test_changed_native_variant_or_ambiguous_selection_is_rejected(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    _, findings, lint = _inputs(root, island)
    with pytest.raises(ValueError, match="distinct named KiCad variants"):
        compare_board_variants(root, "controller", findings, "STANDARD", "standard")
    with pytest.raises(ValueError, match="No complete native population evidence"):
        compare_board_variants(root, "controller", findings, "STANDARD", "UNKNOWN")
    (lint.parent / "alt.board-fitted.csv").write_text("Ref,Val\nR1,1k\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Named variant evidence changed"):
        compare_board_variants(root, "controller", findings, "STANDARD", "ALT")


def test_changed_project_source_invalidates_both_variant_sides(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    _, findings, _ = _inputs(root, island)
    board = island / "kicad/controller.kicad_pcb"
    board.write_bytes(board.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="current findings view"):
        compare_board_variants(root, "controller", findings, "STANDARD", "ALT")


class _BoardVariantParity(McpParityHarness):
    async def _case_cli_mcp(self) -> None:
        _, findings, _ = _inputs(self.root, self.island)
        cli = await self.cli(
            "kicad_tooling.board_variant_compare",
            BoardVariantComparisonReport,
            "--project",
            "controller",
            "--findings-view",
            str(findings),
            "--before-variant",
            "STANDARD",
            "--after-variant",
            "ALT",
            "--output",
            "build/board-variant-comparison/cli",
        )
        arguments = {
            "project_id": "controller",
            "view_id": "mcp",
            "findings_view": findings.relative_to(self.root).as_posix(),
            "before_variant": "STANDARD",
            "after_variant": "ALT",
        }
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(client, "compare_board_variants", BoardVariantComparisonReport, arguments)
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_bytes(),
            (Path(mcp.output_directory) / "index.html").read_bytes(),
        )


def test_cli_mcp_board_variant_comparison_parity() -> None:
    run_mcp_parity(_BoardVariantParity, "_case_cli_mcp")
