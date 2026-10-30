"""Source-bound authored product variant, hierarchy, and harness review parity."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.product_models import ProductRecord
from kicad_tooling.hwrepo.product_visual import build_product_visual
from kicad_tooling.hwrepo.product_visual_models import ProductVisualReport
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity

pytestmark = pytest.mark.template_checkout
PRODUCT = "status-indicator-system"
SOURCE = Path("examples/products/status-indicator-system/product.json")


def test_standard_variant_renders_source_bound_hierarchy_and_harness(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    report = build_product_visual(root, PRODUCT, "STANDARD", Path("build/product-visual/standard"))
    assert report.status == "CURRENT"
    assert not report.build_authorized and not report.observed_wiring
    assert report.product_sha256 == digest(root / SOURCE)
    assert report.system_projection and report.harness_projection
    assert report.harnesses[0].harness_id == "H-STATUS"
    assert report.harnesses[0].electrical_connection_ids == ("C-RETURN", "C-SIGNAL")
    assert {item.path for item in report.instances} >= {"", "UNO", "UNO.J1", "PI", "CABLE", "ENC"}
    assert len(report.projects) >= 2
    assert all(item.status == "CURRENT" and item.source_hashes for item in report.projects)
    assert all(item.config_path in report.source_hashes for item in report.projects)
    assert all(item.origin == "AUTHORED" for item in report.relations)
    output = Path(report.output_directory)
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "All relationships shown are authored product claims" in html
    assert "T-UNO-SIGNAL" in html and "iface-arduino-uno-r3-d13-status-v1" in html
    assert 'href="system.json"' in html and 'href="harness-schedule.json"' in html
    assert (output / "product.json").read_bytes() == (root / SOURCE).read_bytes()
    assert read_model(output / "product-visual.json", ProductVisualReport) == report
    assert all(digest(output / name) == sha for name, sha in report.artifacts_sha256.items())


@pytest.mark.parametrize(
    ("variant", "omitted_path", "omitted_relation"),
    [("UNO_ONLY", "PI", "C-STATUS-ROLE"), ("OPEN_FRAME", "ENC", "C-MOUNT")],
)
def test_variant_omissions_remain_visible(
    tmp_path: Path, variant: str, omitted_path: str, omitted_relation: str
) -> None:
    root, _, _ = parity_workspace(tmp_path)
    report = build_product_visual(root, PRODUCT, variant)
    assert (
        next(item for item in report.instances if item.path == omitted_path).population == "OMITTED"
    )
    assert (
        next(item for item in report.relations if item.id == omitted_relation).population
        == "OMITTED"
    )
    assert any(item.population == "INCLUDED" for item in report.relations)
    html = (Path(report.output_directory) / "index.html").read_text(encoding="utf-8")
    assert "OMITTED" in html and omitted_path in html


def test_broken_terminal_keeps_authored_relation_and_omits_projections(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    path = root / SOURCE
    product = read_model(path, ProductRecord)
    bad = product.connections[0].model_copy(update={"to_terminal": "MISSING-TERMINAL"})
    write_model(path, product.model_copy(update={"connections": (bad, *product.connections[1:])}))
    report = build_product_visual(root, PRODUCT, "STANDARD")
    assert report.status == "REVIEW"
    relation = next(item for item in report.relations if item.id == bad.id)
    assert relation.population == "UNRESOLVED"
    assert relation.to_endpoint.status == "MISSING"
    assert any("ENDPOINT_REF" in issue for issue in report.issues)
    assert not report.system_projection and not report.harness_projection
    output = Path(report.output_directory)
    assert not (output / "system.json").exists()
    assert "MISSING-TERMINAL" in (output / "index.html").read_text(encoding="utf-8")


def test_unknown_part_stays_in_hierarchy_as_unresolved(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    path = root / SOURCE
    product = read_model(path, ProductRecord)
    built = product.assemblies[1]
    bad_member = built.members[0].model_copy(update={"item": "unknown-catalog-part"})
    bad_assembly = built.model_copy(update={"members": (bad_member, *built.members[1:])})
    write_model(
        path,
        product.model_copy(
            update={"assemblies": (product.assemblies[0], bad_assembly, *product.assemblies[2:])}
        ),
    )
    report = build_product_visual(root, PRODUCT, "STANDARD")
    item = next(item for item in report.instances if item.path == "UNO.J1")
    assert item.item == "unknown-catalog-part" and item.kind == "UNRESOLVED"
    assert report.status == "REVIEW" and not report.system_projection
    assert any("PART_REF" in issue for issue in report.issues)


def test_broken_cross_project_binding_is_visible(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    path = root / SOURCE
    product = read_model(path, ProductRecord)
    assembly = product.assemblies[1].model_copy(update={"project_id": "missing-board"})
    write_model(
        path,
        product.model_copy(
            update={"assemblies": (product.assemblies[0], assembly, *product.assemblies[2:])}
        ),
    )
    report = build_product_visual(root, PRODUCT, "STANDARD")
    missing = next(item for item in report.projects if item.project_id == "missing-board")
    assert missing.status == "MISSING"
    assert report.status == "REVIEW"
    assert any("PROJECT_REF" in issue for issue in report.issues)
    assert "missing-board" in (Path(report.output_directory) / "index.html").read_text()


class _ProductVisualParity(McpParityHarness):
    async def _case_test_cli_mcp_product_visual_parity(self) -> None:
        cli = await self.cli(
            "kicad_tooling.product_visual",
            ProductVisualReport,
            "--product",
            PRODUCT,
            "--variant",
            "STANDARD",
            "--output",
            "build/product-visual/cli",
        )
        arguments = {"product_id": PRODUCT, "variant_id": "STANDARD", "view_id": "mcp"}
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue((await client.call_tool("export_product_visual", arguments)).is_error)
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(client, "export_product_visual", ProductVisualReport, arguments)
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_text(),
            (Path(mcp.output_directory) / "index.html").read_text(),
        )


def test_cli_mcp_product_visual_parity() -> None:
    run_mcp_parity(_ProductVisualParity, "_case_test_cli_mcp_product_visual_parity")
