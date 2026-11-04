"""Opt-in exact KiCad acceptance for a named-variant purchasing review."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.findings_view import build_findings_view
from kicad_tooling.hwrepo.models import CheckEvidence, PurchasingReport, ValidationSummary
from kicad_tooling.hwrepo.part_catalog_models import PartRecord, PartsCatalog, PartStatus
from kicad_tooling.hwrepo.pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from kicad_tooling.hwrepo.pcb_variant_population_capture import capture_variant_population
from kicad_tooling.hwrepo.project_models import ComponentIdentity, ProjectKind, ProjectManifest
from kicad_tooling.hwrepo.project_source_hashes import hash_project_sources as hashes
from kicad_tooling.hwrepo.purchasing import plan, read_components
from kicad_tooling.hwrepo.purchasing_preference_models import PurchasingPreferences
from kicad_tooling.hwrepo.variant_parts_review import build_variant_parts_review
from tests.mcp_parity_support import parity_workspace

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="exact KiCad acceptance runs in the opt-in native fixture lane",
    ),
]

FIXTURES = Path(__file__).parent / "fixtures/design_lint"
VARIANT = "Synthetic Assembly A"


@pytest.mark.parametrize(
    ("board_fixture", "fitted"),
    (("board-fitted.kicad_pcb", True), ("board-u1-dnp.kicad_pcb", False)),
)
def test_native_variant_bom_quantities_and_receipt(
    tmp_path: Path, board_fixture: str, fitted: bool
) -> None:
    root, island, _ = parity_workspace(tmp_path)
    manifest_path = island / "project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "toolchain_id": "kicad-10.0.5",
                "component_identity": ComponentIdentity(required=True, part_ids=("probe-part",)),
            }
        ),
    )
    base = island / "kicad/controller"
    shutil.copyfile(
        FIXTURES / "named-variant-population/variant.kicad_pro", base.with_suffix(".kicad_pro")
    )
    shutil.copyfile(
        FIXTURES / "named-variant-population" / board_fixture, base.with_suffix(".kicad_pcb")
    )
    schematic = (FIXTURES / "component-inventory-footprint-identity/control.kicad_sch").read_text(
        encoding="utf-8"
    )
    schematic = schematic.replace(
        '(instances (project "Synthetic PCB footprint identity fixture"',
        '(instances (project "controller"',
    ).replace(
        '    (property "Datasheet" "" (at 76.20 76.20 0)',
        '    (property "PART_ID" "probe-part" (at 76.20 76.20 0)'
        " (effects (font (size 1.27 1.27)) hide))\n"
        '    (property "Datasheet" "" (at 76.20 76.20 0)',
    )
    base.with_suffix(".kicad_sch").write_text(schematic, encoding="utf-8")
    catalog_path = root / "catalog/parts.json"
    write_model(
        catalog_path,
        PartsCatalog(
            schema_version="0.1",
            parts=(
                PartRecord(
                    id="probe-part",
                    revision="A",
                    description="Native variant fixture component",
                    part_class="module",
                    unit="each",
                    manufacturer="Fixture Components",
                    mpn="FCP1001",
                    datasheet_url="https://www.kicad.org/",
                    lifecycle="active",
                    status=PartStatus.APPROVED,
                ),
            ),
        ),
    )
    config = load_config(root, manifest_path)
    current = hashes(root, config.source_roots)
    capture = capture_variant_population(
        root,
        config,
        root / "build/native-variant-capture",
        expected_source_hashes=current,
        kicad_version=config.kicad_version,
    )
    assert capture.coverage.status == "COMPLETE", capture.coverage.issue
    assert len(capture.coverage.evidence) == 1
    variant_export = root / capture.coverage.evidence[0].netlist_path
    components = read_components(variant_export)
    assert [(item.reference, item.part_id) for item in components] == [("U1", "probe-part")]

    native_dir = root / "build/native-variant-summary"
    native_dir.mkdir()
    shutil.copyfile(variant_export, native_dir / "netlist.xml")
    summary_path = native_dir / "summary.json"
    write_model(
        summary_path,
        ValidationSummary(
            timestamp_utc="2026-11-03T00:00:00+00:00",
            checked_commit="LOCAL_UNBOUND",
            project_id="controller",
            project_kind=ProjectKind.PCB,
            checks={
                "source_scope": CheckEvidence(status="PASS", source_hashes=current),
                "source_unchanged": CheckEvidence(status="PASS", source_hashes=current),
                "toolchain": CheckEvidence(
                    status="PASS", observed_version=config.kicad_version, image=config.image
                ),
            },
            status="PASS",
            artifacts_sha256={"netlist.xml": digest(native_dir / "netlist.xml")},
        ),
    )
    lint_dir = root / "build/native-variant-lint"
    lint_dir.mkdir()
    lint_path = lint_dir / "report.json"
    write_model(
        lint_path,
        DesignLintReport(
            status="BLOCKED",
            project_id="controller",
            source_hashes=current,
            netlist_sha256=digest(native_dir / "netlist.xml"),
            native_summary=summary_path.relative_to(root).as_posix(),
            pcb_component_inventory=PcbComponentInventoryCoverageReport(
                variant_population=capture.coverage
            ),
        ),
    )
    findings = build_findings_view(
        root, "controller", summary_path, Path("build/native-variant-findings"), lint_path
    )
    parts_dir = root / "build/native-variant-parts"
    parts_dir.mkdir()
    shutil.copyfile(variant_export, parts_dir / "netlist.xml")
    purchase_plan = plan(
        components,
        read_model(catalog_path, PartsCatalog),
        PurchasingPreferences(boards=2, spare_percent=0, spare_minimum=0),
        ("probe-part",),
    )
    parts_path = parts_dir / "report.json"
    write_model(
        parts_path,
        PurchasingReport(
            project_id="controller",
            status=purchase_plan.status,
            plan=purchase_plan,
            source_hashes=current,
            input_hashes={
                catalog_path.relative_to(root).as_posix(): digest(catalog_path),
                manifest_path.relative_to(root).as_posix(): digest(manifest_path),
            },
            netlist_sha256=digest(parts_dir / "netlist.xml"),
            receipt_dir=str(parts_dir),
        ),
    )
    report = build_variant_parts_review(
        root,
        "controller",
        parts_path,
        Path(findings.output_directory) / "review.json",
        VARIANT,
    )
    assert report.assembly_variant == VARIANT
    if fitted:
        assert report.unresolved == ()
        assert [
            (line.part_id, line.references, line.per_board, line.required)
            for line in report.plan.lines
        ] == [("probe-part", ("U1",), 1, 2)]
        assert report.plan.status == "READY_FOR_ORDER_REVIEW"
        assert (Path(report.output_directory) / "digikey.csv").is_file()
    else:
        assert [(item.reference, item.reason) for item in report.unresolved] == [
            ("U1", "Fitted schematic component has no fitted PCB position.")
        ]
        assert report.plan.lines == ()
        assert report.plan.status == "NEEDS_PARTS"
        assert not (Path(report.output_directory) / "digikey.csv").exists()
