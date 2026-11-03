"""Named-variant BOM reconciliation, retained review, and CLI/MCP parity."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.cross_probe_models import CrossProbeReport
from kicad_tooling.hwrepo.discovery import load_registry
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import PurchasingReport
from kicad_tooling.hwrepo.variant_parts_review import build_variant_parts_review
from kicad_tooling.hwrepo.variant_parts_review_models import VariantPartsReviewReport
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity
from tests.test_cross_probe_variant import _inputs

pytestmark = pytest.mark.template_checkout


def _review_inputs(root: Path, island: Path) -> tuple[Path, Path, Path]:
    parts, findings, lint = _inputs(root, island)
    saved = read_model(parts, PurchasingReport)
    catalog = load_registry(root).catalogs.parts
    write_model(
        parts,
        saved.model_copy(
            update={"input_hashes": {**saved.input_hashes, catalog: digest(root / catalog)}}
        ),
    )
    return parts, findings, lint


def test_named_variants_reconcile_distinct_populations(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    parts, findings, _ = _review_inputs(root, island)
    standard = build_variant_parts_review(root, "controller", parts, findings, "STANDARD")
    alternate = build_variant_parts_review(root, "controller", parts, findings, "ALT")
    assert standard.assembly_variant == "STANDARD"
    assert alternate.assembly_variant == "ALT"
    assert {item.reference for item in standard.plan.components} >= {"R1", "R2"}
    assert {item.reference for item in alternate.plan.components} >= {"R1", "R2"}
    assert set(standard.plan.excluded_references) == {"C1", "R2"}
    assert set(alternate.plan.excluded_references) == {"C1", "R1"}
    assert {item.reference for item in standard.unresolved} == {"J9"}
    assert {item.reference for item in alternate.unresolved} == {"J9"}
    assert standard.plan.status == alternate.plan.status == "NEEDS_PARTS"
    for report in (standard, alternate):
        directory = Path(report.output_directory)
        assert not (directory / "digikey.csv").exists()
        assert (directory / "bom.csv").exists()
        assert "J9" in (directory / "unresolved.csv").read_text(encoding="utf-8")
        assert "navigation/index.html" in (directory / "index.html").read_text(encoding="utf-8")
        assert read_model(directory / "variant-parts.json", VariantPartsReviewReport) == report
        navigation = read_model(directory / "navigation/cross-probe.json", CrossProbeReport)
        assert navigation.assembly_variant == report.assembly_variant


def test_changed_native_variant_export_is_rejected(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    parts, findings, lint = _review_inputs(root, island)
    (lint.parent / "standard.board-fitted.csv").write_text("Ref,Val\nR2,2k\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Named variant evidence changed"):
        build_variant_parts_review(root, "controller", parts, findings, "STANDARD")


def test_changed_parts_catalog_is_rejected(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    parts, findings, _ = _review_inputs(root, island)
    catalog = root / load_registry(root).catalogs.parts
    catalog.write_bytes(catalog.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="catalog or preferences are stale"):
        build_variant_parts_review(root, "controller", parts, findings, "STANDARD")


def test_variant_quantities_follow_fitted_native_identity(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    parts, findings, _ = _review_inputs(root, island)
    standard = build_variant_parts_review(root, "controller", parts, findings, "STANDARD")
    alternate = build_variant_parts_review(root, "controller", parts, findings, "ALT")
    assert [(line.part_id, line.references, line.per_board) for line in standard.plan.lines] == [
        ("resistor-1k", ("R1",), 1)
    ]
    assert alternate.plan.lines == ()
    assert any(
        item.code == "UNKNOWN_PART_ID" and item.references == ("R2",)
        for item in alternate.plan.findings
    )
    assert standard.plan.status == alternate.plan.status == "NEEDS_PARTS"
    assert not (Path(standard.output_directory) / "digikey.csv").exists()


def test_variant_only_schematic_reference_gets_navigation_entry(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    parts, findings, _ = _review_inputs(root, island)
    saved = read_model(parts, PurchasingReport)
    assert saved.plan is not None
    trimmed = saved.plan.model_copy(
        update={
            "components": tuple(item for item in saved.plan.components if item.reference != "R2")
        }
    )
    write_model(parts, saved.model_copy(update={"plan": trimmed}))
    report = build_variant_parts_review(root, "controller", parts, findings, "ALT")
    navigation = read_model(
        Path(report.output_directory) / "navigation/cross-probe.json", CrossProbeReport
    )
    r2 = next(item for item in navigation.entries if item.reference == "R2")
    assert r2.origin == "VARIANT_NATIVE"
    assert r2.variant_board == "FITTED"
    assert r2.board
    assert "R2" in (Path(report.output_directory) / "index.html").read_text(encoding="utf-8")


class _VariantPartsParity(McpParityHarness):
    async def _case_variant_parts(self) -> None:
        parts, findings, _ = _review_inputs(self.root, self.island)
        cli = await self.cli(
            "kicad_tooling.variant_parts_review",
            VariantPartsReviewReport,
            "--project",
            "controller",
            "--parts-report",
            str(parts),
            "--findings-view",
            str(findings),
            "--assembly-variant",
            "ALT",
            "--output",
            "build/variant-parts/cli",
        )
        arguments = {
            "project_id": "controller",
            "view_id": "mcp",
            "parts_report": parts.relative_to(self.root).as_posix(),
            "findings_view": findings.relative_to(self.root).as_posix(),
            "assembly_variant": "ALT",
        }
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client, "export_variant_parts_review", VariantPartsReviewReport, arguments
            )
        self.assertNotEqual(cli.output_directory, mcp.output_directory)
        for key in ("output_directory", "navigation_report", "navigation_report_sha256"):
            cli = cli.model_copy(update={key: getattr(mcp, key)})
        self.assertEqual(cli, mcp)
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_bytes(),
            (Path(mcp.output_directory) / "index.html").read_bytes(),
        )


def test_variant_parts_cli_mcp_parity() -> None:
    run_mcp_parity(_VariantPartsParity, "_case_variant_parts")
