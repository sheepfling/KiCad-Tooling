"""Source-bound BOM differences and CLI/MCP comparison parity."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.bom_compare import compare_bom
from kicad_tooling.hwrepo.bom_compare_models import BomComparisonReport
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    PurchasingComponent,
    PurchasingFinding,
    PurchasingLine,
    PurchasingPlan,
    PurchasingReport,
)
from kicad_tooling.hwrepo.purchasing_preference_models import PurchasingPreferences
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity

pytestmark = pytest.mark.template_checkout


def line(part_id: str, revision: str, references: tuple[str, ...], quantity: int) -> PurchasingLine:
    return PurchasingLine(
        part_id=part_id,
        revision=revision,
        manufacturer="Mfg",
        mpn=part_id,
        footprint="Res:F",
        references=references,
        per_board=len(references),
        required=quantity,
        spares=0,
        quantity=quantity,
        order_number=part_id,
        order_number_kind="MPN",
        search_url="https://example.com/part",
    )


def plan(*, later: bool) -> PurchasingPlan:
    if later:
        components = (
            PurchasingComponent(reference="R1", value="2k", footprint="Res:F", part_id="RES-2"),
            PurchasingComponent(reference="R2", value="1k", footprint="Res:F", part_id="RES-1"),
            PurchasingComponent(
                reference="R4", value="<unsafe>", footprint="Res:F", part_id="RES-1", dnp=True
            ),
        )
        lines = (line("RES-2", "B", ("R1",), 2), line("RES-1", "A", ("R2",), 2))
        findings = ()
    else:
        components = (
            PurchasingComponent(reference="R1", value="1k", footprint="Res:F", part_id="RES-1"),
            PurchasingComponent(
                reference="R2", value="1k", footprint="Res:F", part_id="RES-1", dnp=True
            ),
            PurchasingComponent(reference="R3", value="?", footprint="Res:F"),
        )
        lines = (line("RES-1", "A", ("R1",), 1),)
        findings = (
            PurchasingFinding(
                code="MISSING_PART_ID",
                references=("R3",),
                message="Unresolved",
                action="Choose an exact part",
            ),
        )
    return PurchasingPlan(
        status="NEEDS_PARTS",
        preferences=PurchasingPreferences(),
        components=components,
        lines=lines,
        findings=findings,
        excluded_references=("R4",) if later else ("R2",),
    )


def save_parts(root: Path, name: str, *, later: bool, changed_scope: bool = False) -> Path:
    directory = root / "build/parts" / name
    directory.mkdir(parents=True)
    netlist = directory / "netlist.xml"
    netlist.write_text("<export><components/></export>", encoding="utf-8")
    source_name = (
        "examples/projects/controller/kicad/other.kicad_sch"
        if changed_scope
        else "examples/projects/controller/kicad/controller.kicad_sch"
    )
    report = PurchasingReport(
        project_id="controller",
        status="NEEDS_PARTS",
        plan=plan(later=later),
        source_hashes={source_name: "a" * 64 if not later else "b" * 64},
        input_hashes={"examples/projects/controller/project.json": "c" * 64},
        netlist_sha256=hashlib.sha256(netlist.read_bytes()).hexdigest(),
        receipt_dir=str(directory),
        artifacts=("bom.csv",),
    )
    write_model(directory / "report.json", report)
    return directory / "report.json"


def test_comparison_shows_reference_population_identity_and_quantity(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    before = save_parts(root, "before", later=False)
    after = save_parts(root, "after", later=True, changed_scope=True)
    report = compare_bom(root, "controller", before, after, Path("build/bom-comparison/view"))
    assert [(item.reference, item.change) for item in report.references] == [
        ("R1", "CHANGED"),
        ("R2", "CHANGED"),
        ("R3", "REMOVED"),
        ("R4", "ADDED"),
    ]
    assert report.references[0].before and report.references[0].before.revision == "A"
    assert report.references[0].after and report.references[0].after.revision == "B"
    assert report.references[1].before and report.references[1].before.population == "DNP"
    assert report.references[2].before and report.references[2].before.population == "UNRESOLVED"
    assert report.references[3].after and report.references[3].after.population == "DNP"
    assert report.source_scope == "DIFFERENT_PATHS" and report.variant_scope == "NOT_RECORDED"
    assert [(item.part_id, item.revision, item.change) for item in report.quantities] == [
        ("RES-1", "A", "CHANGED"),
        ("RES-2", "B", "ADDED"),
    ]
    directory = Path(report.output_directory)
    html = (directory / "index.html").read_text(encoding="utf-8")
    assert "&lt;unsafe&gt;" in html and "<unsafe>" not in html
    assert read_model(directory / "comparison.json", BomComparisonReport) == report


def test_rejects_changed_or_incompatible_receipts(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    before = save_parts(root, "before", later=False)
    after = save_parts(root, "after", later=True)
    with pytest.raises(ValueError, match="distinct"):
        compare_bom(root, "controller", before, before)
    (after.parent / "netlist.xml").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="netlist"):
        compare_bom(root, "controller", before, after)
    wrong = read_model(after, PurchasingReport).model_copy(update={"project_id": "other"})
    write_model(after, wrong)
    with pytest.raises(ValueError, match="another project"):
        compare_bom(root, "controller", before, after)


def test_rejects_duplicate_reference_in_saved_plan(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    before = save_parts(root, "before", later=False)
    after = save_parts(root, "after", later=True)
    saved = read_model(after, PurchasingReport)
    assert saved.plan is not None
    repeated = saved.plan.model_copy(
        update={"components": (*saved.plan.components, saved.plan.components[0])}
    )
    write_model(after, saved.model_copy(update={"plan": repeated}))
    with pytest.raises(ValueError, match="repeats component reference"):
        compare_bom(root, "controller", before, after)


class _BomParity(McpParityHarness):
    async def _case_test_cli_mcp_bom_compare_parity(self) -> None:
        before = save_parts(self.root, "before", later=False)
        after = save_parts(self.root, "after", later=True)
        cli = await self.cli(
            "kicad_tooling.bom_compare",
            BomComparisonReport,
            "--project",
            "controller",
            "--before",
            str(before),
            "--after",
            str(after),
            "--output",
            "build/bom-comparison/cli",
        )
        arguments = {
            "project_id": "controller",
            "view_id": "mcp",
            "before": before.relative_to(self.root).as_posix(),
            "after": after.relative_to(self.root).as_posix(),
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue((await client.call_tool("compare_parts_bom", arguments)).is_error)
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(client, "compare_parts_bom", BomComparisonReport, arguments)
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_bytes(),
            (Path(mcp.output_directory) / "index.html").read_bytes(),
        )


def test_cli_mcp_bom_compare_parity() -> None:
    run_mcp_parity(_BomParity, "_case_test_cli_mcp_bom_compare_parity")
