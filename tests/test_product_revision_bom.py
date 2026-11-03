"""Historical product views compare retained source, instances, and BOM rows."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.part_catalog_models import PartsCatalog
from kicad_tooling.hwrepo.product_models import ProductRecord
from kicad_tooling.hwrepo.product_revision_bom import compare_product_revisions
from kicad_tooling.hwrepo.product_revision_bom_models import ProductRevisionBomReport
from kicad_tooling.hwrepo.product_visual import build_product_visual
from kicad_tooling.hwrepo.product_visual_models import ProductVisualReport
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity

pytestmark = pytest.mark.template_checkout
PRODUCT = "status-indicator-system"
PRODUCT_SOURCE = "examples/products/status-indicator-system/product.json"
PARTS_SOURCE = "catalog/parts.json"


def _views(root: Path) -> tuple[Path, Path]:
    before = build_product_visual(
        root, PRODUCT, "STANDARD", Path("build/product-visual/revision-before")
    )
    product_path = root / PRODUCT_SOURCE
    product = read_model(product_path, ProductRecord)
    standard = product.variants[0].model_copy(update={"revision": "B"})
    root_assembly = product.assemblies[0]
    spare = root_assembly.members[0].model_copy(
        update={"ref": "SPARE", "item": "training-generic-resistor-1k-th", "quantity": 2}
    )
    updated_root = root_assembly.model_copy(
        update={"revision": "B", "members": (*root_assembly.members, spare)}
    )
    write_model(
        product_path,
        product.model_copy(
            update={
                "revision": "B",
                "variants": (standard, *product.variants[1:]),
                "assemblies": (updated_root, *product.assemblies[1:]),
            }
        ),
    )
    catalog_path = root / PARTS_SOURCE
    catalog = read_model(catalog_path, PartsCatalog)
    first_part = catalog.parts[0].model_copy(update={"revision": "B"})
    write_model(
        catalog_path, catalog.model_copy(update={"parts": (first_part, *catalog.parts[1:])})
    )
    after = build_product_visual(
        root, PRODUCT, "STANDARD", Path("build/product-visual/revision-after")
    )
    return Path(before.output_directory) / "product-visual.json", Path(
        after.output_directory
    ) / "product-visual.json"


def test_saved_revisions_compare_historical_quantities_and_part_revisions(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    before, after = _views(root)
    report = compare_product_revisions(
        root, before, after, Path("build/product-revision-bom/comparison")
    )
    assert report.status == "COMPARED" and report.bom_projection, report.issues
    assert report.variant_relation == "SAME"
    assert report.baseline.source_relation == "HISTORICAL"
    assert report.candidate.source_relation == "CURRENT"
    assert report.baseline.product_revision == "A" and report.candidate.product_revision == "B"
    assert report.baseline.parts_catalog_sha256 != report.candidate.parts_catalog_sha256
    header = [item for item in report.parts if item.part_id.endswith("header-1x02-2.54")]
    assert [(item.revision, item.change) for item in header] == [("A", "REMOVED"), ("B", "ADDED")]
    assert header[0].before and header[0].before.quantity == 2
    assert header[1].after and header[1].after.quantity == 2
    resistor = next(item for item in report.parts if item.part_id.endswith("resistor-1k-th"))
    assert resistor.before and resistor.after
    assert (resistor.before.quantity, resistor.after.quantity) == (2, 4)
    spare = next(item for item in report.instances if item.path == "SPARE")
    assert spare.change == "ADDED" and spare.before is None and spare.after is not None
    assert (
        read_model(Path(report.output_directory) / "comparison.json", ProductRevisionBomReport)
        == report
    )
    assert (
        digest(Path(report.output_directory) / "index.html")
        == report.artifacts_sha256["index.html"]
    )


def test_changed_saved_catalog_is_rejected(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    before, after = _views(root)
    (before.parent / "parts-catalog.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact changed"):
        compare_product_revisions(root, before, after)


def test_saved_instance_must_match_retained_product(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    before, after = _views(root)
    view = read_model(before, ProductVisualReport)
    write_model(before, view.model_copy(update={"instances": ()}))
    with pytest.raises(ValueError, match="instances differ"):
        compare_product_revisions(root, before, after)


def test_differing_saved_variant_is_labeled(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    standard = build_product_visual(
        root, PRODUCT, "STANDARD", Path("build/product-visual/standard")
    )
    uno_only = build_product_visual(root, PRODUCT, "UNO_ONLY", Path("build/product-visual/uno"))
    report = compare_product_revisions(
        root,
        Path(standard.output_directory) / "product-visual.json",
        Path(uno_only.output_directory) / "product-visual.json",
    )
    assert report.variant_relation == "DIFFERENT"
    assert report.product_path_relation == "SAME"
    assert report.bom_projection


def test_legacy_view_retains_instances_without_claiming_bom(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    before, after = _views(root)
    view = read_model(before, ProductVisualReport)
    (before.parent / "parts-catalog.json").unlink()
    artifacts = {
        key: sha for key, sha in view.artifacts_sha256.items() if key != "parts-catalog.json"
    }
    write_model(
        before,
        view.model_copy(
            update={
                "parts_catalog_path": None,
                "parts_catalog_sha256": None,
                "artifacts_sha256": artifacts,
            }
        ),
    )
    report = compare_product_revisions(root, before, after)
    assert report.status == "REVIEW" and not report.bom_projection and not report.parts
    assert report.instances
    assert any("predates retained parts catalogs" in issue for issue in report.issues)


class _RevisionParity(McpParityHarness):
    async def _case_test_cli_mcp_product_revision_bom_parity(self) -> None:
        before, after = _views(self.root)
        old, new = before.relative_to(self.root).as_posix(), after.relative_to(self.root).as_posix()
        cli = await self.cli(
            "kicad_tooling.product_revision_bom",
            ProductRevisionBomReport,
            "--baseline",
            old,
            "--candidate",
            new,
            "--output",
            "build/product-revision-bom/cli",
        )
        arguments = {"baseline": old, "candidate": new, "view_id": "mcp"}
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue(
                (await client.call_tool("compare_product_revision_bom", arguments)).is_error
            )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client, "compare_product_revision_bom", ProductRevisionBomReport, arguments
            )
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_bytes(),
            (Path(mcp.output_directory) / "index.html").read_bytes(),
        )


def test_cli_mcp_product_revision_bom_parity() -> None:
    run_mcp_parity(_RevisionParity, "_case_test_cli_mcp_product_revision_bom_parity")
