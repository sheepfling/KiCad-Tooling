"""Dated offer comparisons keep packaging, currency, and identity limits visible."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, repo_path, write_model
from kicad_tooling.hwrepo.discovery import load_registry
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    PurchasingComponent,
    PurchasingLine,
    PurchasingPlan,
    PurchasingReport,
)
from kicad_tooling.hwrepo.part_catalog_models import PartsCatalog
from kicad_tooling.hwrepo.purchasing_preference_models import PurchasingPreferences
from kicad_tooling.hwrepo.sourcing_models import SourcingSnapshot, SupplierOffer
from kicad_tooling.hwrepo.supplier_analysis import compare_supplier_snapshots
from kicad_tooling.hwrepo.supplier_analysis_models import SupplierAnalysisReport
from kicad_tooling.hwrepo.verification_history_evidence import current_source
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity

pytestmark = pytest.mark.template_checkout


def _inputs(root: Path, *, unresolved: bool = False) -> tuple[Path, Path, Path, str]:
    catalog = load_registry(root).catalogs.parts
    part_id = read_model(repo_path(root, catalog), PartsCatalog).parts[0].id
    current, _ = current_source(root, "controller")
    source_path, source_hash = next(iter(current.items()))
    directory = root / "build/parts/supplier-analysis"
    directory.mkdir(parents=True)
    netlist = directory / "netlist.xml"
    netlist.write_text("<export><components/></export>", encoding="utf-8")
    components = (
        PurchasingComponent(reference="R1", value="1k", footprint="Res:F", part_id=part_id),
        *(
            (PurchasingComponent(reference="R2", value="?", footprint="Res:F"),)
            if unresolved
            else ()
        ),
    )
    line = PurchasingLine(
        part_id=part_id,
        revision="A",
        manufacturer="Example",
        mpn="EXAMPLE-1",
        footprint="Res:F",
        references=("R1",),
        per_board=1,
        required=7,
        spares=0,
        quantity=7,
        order_number="EXAMPLE-1",
        order_number_kind="MPN",
        search_url="https://example.invalid/part",
    )
    parts = PurchasingReport(
        project_id="controller",
        status="NEEDS_PARTS" if unresolved else "READY_FOR_ORDER_REVIEW",
        plan=PurchasingPlan(
            status="NEEDS_PARTS" if unresolved else "READY_FOR_ORDER_REVIEW",
            preferences=PurchasingPreferences(),
            components=components,
            lines=(line,),
            findings=(),
        ),
        source_hashes={source_path: source_hash},
        input_hashes={
            "examples/projects/controller/project.json": digest(
                root / "examples/projects/controller/project.json"
            )
        },
        netlist_sha256=digest(netlist),
        receipt_dir=str(directory),
    )
    receipt = directory / "report.json"
    write_model(receipt, parts)

    def offer(
        offer_id: str,
        supplier: str,
        currency: str,
        price: int | None,
        minimum: int | None,
        multiple: int | None,
    ) -> SupplierOffer:
        return SupplierOffer(
            id=offer_id,
            part_id=part_id,
            supplier=supplier,
            supplier_sku=f"{supplier}-SKU",
            source_url="https://example.invalid/offer",
            region="US",
            currency=currency,
            quantity_break=5,
            unit_price_minor=price,
            availability="recorded availability only",
            minimum_order_quantity=minimum,
            package_multiple=multiple,
        )

    old = SourcingSnapshot(
        snapshot_id="supplier-before",
        source_commit="a" * 40,
        observed_at=datetime(2026, 10, 20, tzinfo=UTC),
        offers=(offer("usd-before", "Supplier-A", "USD", 120, 10, 5),),
    )
    new = SourcingSnapshot(
        snapshot_id="supplier-after",
        source_commit="b" * 40,
        observed_at=datetime(2026, 10, 29, tzinfo=UTC),
        offers=(
            offer("usd-after", "Supplier-A", "USD", 100, 10, 5),
            offer("eur-missing", "Supplier-B", "EUR", None, 1, 1),
            offer("usd-unknown-pack", "Supplier-C", "USD", 110, None, None),
        ),
    )
    before = root / "build/sourcing/before.json"
    after = root / "build/sourcing/after.json"
    before.parent.mkdir(parents=True)
    write_model(before, old)
    write_model(after, new)
    return receipt, before, after, part_id


def test_dated_offers_packaging_currency_and_missing_fields(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    parts, before, after, part_id = _inputs(root)
    report = compare_supplier_snapshots(
        root,
        "controller",
        parts,
        before,
        after,
        date(2026, 10, 30),
        3,
        Path("build/supplier-analysis/control"),
    )
    assert report.before.freshness == "STALE" and report.after.freshness == "CURRENT"
    assert report.before.validation_status == report.after.validation_status == "PASS"
    assert report.parts_source_current
    assert report.currencies == ("EUR", "USD")
    prices = {item.supplier: item for item in report.offers}
    before_cost = prices["Supplier-A"].before
    after_cost = prices["Supplier-A"].after
    assert before_cost is not None and after_cost is not None
    assert before_cost.part_id == part_id and before_cost.order_quantity == 10
    assert before_cost.extended_minor == 1200 and after_cost.extended_minor == 1000
    assert before_cost.requested_quantity == 7
    assert prices["Supplier-B"].after is not None
    assert prices["Supplier-B"].after.status == "MISSING_PRICE"
    assert prices["Supplier-C"].after is not None
    assert prices["Supplier-C"].after.status == "PACKAGING_UNKNOWN"
    assert any("multiple currencies" in issue for issue in report.issues)
    assert not report.purchase_authorized and not report.build_authorized
    output = Path(report.output_directory)
    assert read_model(output / "supplier-analysis.json", SupplierAnalysisReport) == report
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "Extended 1,200 USD minor units" in html and "unavailable" in html
    for name, checksum in report.artifacts_sha256.items():
        assert digest(output / name) == checksum


def test_unresolved_identity_and_source_change(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    parts, before, after, _ = _inputs(root, unresolved=True)
    report = compare_supplier_snapshots(
        root,
        "controller",
        parts,
        before,
        after,
        date(2026, 10, 30),
        20,
        Path("build/supplier-analysis/unresolved"),
    )
    assert report.unresolved_references == ("R2",)
    assert report.before.freshness == "CURRENT"
    assert any("Fitted references lack" in issue for issue in report.issues)
    source_name = next(iter(report.parts_source_hashes))
    (root / source_name).write_text("changed", encoding="utf-8")
    stale = compare_supplier_snapshots(
        root,
        "controller",
        parts,
        before,
        after,
        date(2026, 10, 30),
        20,
        Path("build/supplier-analysis/stale-source"),
    )
    assert not stale.parts_source_current


class _SupplierParity(McpParityHarness):
    async def _case_test_cli_mcp_supplier_analysis_parity(self) -> None:
        parts, before, after, _ = _inputs(self.root)
        cli = await self.cli(
            "kicad_tooling.supplier_analysis",
            SupplierAnalysisReport,
            "--project",
            "controller",
            "--parts-receipt",
            str(parts),
            "--before",
            str(before),
            "--after",
            str(after),
            "--as-of",
            "2026-10-30",
            "--max-age-days",
            "3",
            "--output",
            "build/supplier-analysis/cli",
        )
        arguments = {
            "project_id": "controller",
            "view_id": "mcp",
            "parts_receipt": parts.relative_to(self.root).as_posix(),
            "before": before.relative_to(self.root).as_posix(),
            "after": after.relative_to(self.root).as_posix(),
            "as_of": "2026-10-30",
            "max_age_days": 3,
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue((await client.call_tool("compare_supplier_offers", arguments)).is_error)
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client, "compare_supplier_offers", SupplierAnalysisReport, arguments
            )
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_bytes(),
            (Path(mcp.output_directory) / "index.html").read_bytes(),
        )


def test_cli_mcp_supplier_analysis_parity() -> None:
    run_mcp_parity(_SupplierParity, "_case_test_cli_mcp_supplier_analysis_parity")
