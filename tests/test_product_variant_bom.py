"""Authored variant BOM changes, incomplete contracts, and CLI/MCP parity."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo import product_variant_bom as variant_service
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.product_models import ProductRecord
from kicad_tooling.hwrepo.product_variant_bom import compare_product_variants
from kicad_tooling.hwrepo.product_variant_bom_models import ProductVariantBomReport
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity

pytestmark = pytest.mark.template_checkout
PRODUCT = "status-indicator-system"
SOURCE = Path("examples/products/status-indicator-system/product.json")


def test_variant_population_and_canonical_quantities(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    report = compare_product_variants(
        root, PRODUCT, "STANDARD", "UNO_ONLY", Path("build/product-variant-bom/compare")
    )
    assert report.status == "CURRENT" and report.bom_projection
    assert not report.build_authorized and not report.purchase_authorized
    assert report.product_sha256 == digest(root / SOURCE)
    pi = next(item for item in report.instances if item.path == "PI.J1")
    assert pi.change == "CHANGED"
    assert pi.before.population == "INCLUDED" and pi.after.population == "OMITTED"
    header = next(item for item in report.parts if item.part_id.endswith("header-1x02-2.54"))
    assert header.change == "CHANGED" and header.before and header.after
    assert (header.before.quantity, header.after.quantity) == (2, 1)
    assert "PI.J1" in header.before.instances and "PI.J1" not in header.after.instances
    directory = Path(report.output_directory)
    assert read_model(directory / "comparison.json", ProductVariantBomReport) == report
    assert all(digest(directory / name) == sha for name, sha in report.artifacts_sha256.items())
    html = (directory / "index.html").read_text(encoding="utf-8")
    assert 'href="before/index.html"' in html and 'href="after/index.html"' in html
    assert "PI.J1" in html and "Grouped parts" in html


def test_variant_removes_purchased_and_direct_part(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    report = compare_product_variants(root, PRODUCT, "STANDARD", "OPEN_FRAME")
    enclosure = next(item for item in report.parts if item.part_id.endswith("enclosure"))
    assert enclosure.change == "REMOVED" and enclosure.after is None
    cable = next(item for item in report.instances if item.path == "CABLE")
    assert cable.before.part_id == "training-generic-cable"
    assert cable.change == "UNCHANGED"


def test_unknown_part_keeps_unresolved_instance_and_blocks_bom(tmp_path: Path) -> None:
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
    report = compare_product_variants(root, PRODUCT, "STANDARD", "UNO_ONLY")
    assert report.status == "REVIEW" and not report.bom_projection and not report.parts
    unresolved = next(item for item in report.instances if item.path == "UNO.J1")
    assert unresolved.before.population == "UNRESOLVED"
    assert unresolved.before.part_id is None
    assert any("PART_REF" in issue for issue in report.issues)


def test_distinct_declared_variants_required(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    with pytest.raises(ValueError, match="distinct"):
        compare_product_variants(root, PRODUCT, "STANDARD", "STANDARD")
    with pytest.raises(ValueError, match="declared product variant"):
        compare_product_variants(root, PRODUCT, "STANDARD", "UNKNOWN")


def test_product_source_change_between_variant_views_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, _ = parity_workspace(tmp_path)
    original = variant_service.build_product_visual

    def changed_source(root: Path, product_id: str, variant_id: str, output: Path):
        result = original(root, product_id, variant_id, output)
        if variant_id == "STANDARD":
            path = root / SOURCE
            product = read_model(path, ProductRecord)
            write_model(path, product.model_copy(update={"revision": "B"}))
        return result

    monkeypatch.setattr(variant_service, "build_product_visual", changed_source)
    with pytest.raises(ValueError, match="same product source revision"):
        compare_product_variants(root, PRODUCT, "STANDARD", "UNO_ONLY")


class _ProductVariantParity(McpParityHarness):
    async def _case_test_cli_mcp_product_variant_bom_parity(self) -> None:
        cli = await self.cli(
            "kicad_tooling.product_variant_bom",
            ProductVariantBomReport,
            "--product",
            PRODUCT,
            "--before-variant",
            "STANDARD",
            "--after-variant",
            "UNO_ONLY",
            "--output",
            "build/product-variant-bom/cli",
        )
        arguments = {
            "product_id": PRODUCT,
            "before_variant": "STANDARD",
            "after_variant": "UNO_ONLY",
            "view_id": "mcp",
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue(
                (await client.call_tool("compare_product_variant_bom", arguments)).is_error
            )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client, "compare_product_variant_bom", ProductVariantBomReport, arguments
            )
        self.assertEqual(cli.source_hashes, mcp.source_hashes)
        self.assertEqual(cli.instances, mcp.instances)
        self.assertEqual(cli.parts, mcp.parts)
        self.assertEqual(cli.issues, mcp.issues)
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_text(),
            (Path(mcp.output_directory) / "index.html").read_text(),
        )


def test_cli_mcp_product_variant_bom_parity() -> None:
    run_mcp_parity(_ProductVariantParity, "_case_test_cli_mcp_product_variant_bom_parity")
