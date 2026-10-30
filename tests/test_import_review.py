"""Onboarding review keeps source, dependency, and apply decisions explicit."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.import_review import apply_reviewed_import, build_import_review
from kicad_tooling.hwrepo.import_review_models import ImportReviewReport
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.project_models import ProjectImportReport
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity

pytestmark = pytest.mark.template_checkout


def _source(base: Path) -> Path:
    directory = base / "Incoming board"
    directory.mkdir()
    project = directory / "Power board.kicad_pro"
    project.write_text("{}", encoding="utf-8")
    project.with_suffix(".kicad_sch").write_text("(kicad_sch)", encoding="utf-8")
    project.with_suffix(".kicad_pcb").write_text(
        '(kicad_pcb\n(model "${KIPRJMOD}/models/case.step")\n'
        '(model "${KICAD10_3DMODEL_DIR}/Connector.3dshapes/body.step"))',
        encoding="utf-8",
    )
    (directory / "models").mkdir()
    (directory / "models/case.step").write_text("STEP source", encoding="utf-8")
    return project


def test_supported_source_lists_files_dependencies_and_applies_review(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    source = _source(tmp_path)
    review = build_import_review(
        root, source, "power-board", "kicad-10.0.5", Path("build/import-review/power")
    )
    assert review.status == "PREVIEW_CLEAR"
    assert review.preview.status == "PASS" and review.preview.dry_run
    assert review.source_project_sha256 == review.preview.copied_sha256[source.name]
    assert {item.disposition for item in review.files} == {"INCLUDED"}
    assert {item.status for item in review.dependencies} == {"PROJECT_LOCAL", "PINNED_LIBRARY"}
    assert review.toolchain is not None and review.toolchain.kicad_version == "10.0.5"
    assert review.repository_inputs_sha256
    assert not (root / "projects/power-board").exists()
    output = Path(review.output_directory)
    assert read_model(output / "review.json", ImportReviewReport) == review
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "Source files" in html and "CAD libraries and models" in html
    assert "${KIPRJMOD}" in html and "PINNED_LIBRARY" in html
    applied = apply_reviewed_import(root, source, "power-board", "kicad-10.0.5", output)
    assert applied.status == "PASS" and not applied.dry_run
    assert (root / applied.directory / "kicad" / source.name).read_bytes() == source.read_bytes()


def test_missing_dependency_is_a_blocking_review_action(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    source = _source(tmp_path)
    (source.parent / "models/case.step").unlink()
    review = build_import_review(root, source, "power-board", "kicad-10.0.5")
    assert review.status == "NEEDS_WORK"
    assert review.preview.status == "PASS"
    assert any(item.status == "MISSING" for item in review.dependencies)
    assert any(item.code == "CAD_PATH" for item in review.diagnosis.findings)
    with pytest.raises(ValueError, match="clear source"):
        apply_reviewed_import(
            root, source, "power-board", "kicad-10.0.5", Path(review.output_directory)
        )


def test_conflicting_id_and_nonportable_path_remain_visible(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    source = _source(tmp_path)
    collision = build_import_review(root, source, "controller", "kicad-10.0.5")
    assert collision.status == "NEEDS_WORK"
    assert any("already exists" in item for item in collision.issues)
    source.with_suffix(".kicad_pcb").write_text(
        '(kicad_pcb (model "C:\\Users\\me\\model.step"))', encoding="utf-8"
    )
    nonportable = build_import_review(root, source, "power-board", "kicad-10.0.5")
    assert nonportable.status == "NEEDS_WORK"
    assert nonportable.dependencies[0].status == "NONPORTABLE"
    assert any("machine-local" in item.observed for item in nonportable.diagnosis.findings)


def test_unsupported_format_and_missing_sheet_are_reviewed(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    source = _source(tmp_path)
    unsupported = source.with_suffix(".dsn")
    unsupported.write_text("foreign source", encoding="utf-8")
    report = build_import_review(root, unsupported, "foreign-board", "kicad-10.0.5")
    assert report.status == "UNSUPPORTED_FORMAT"
    assert any(item.disposition == "UNSUPPORTED" for item in report.files)
    source.with_suffix(".kicad_sch").write_text(
        '(kicad_sch (property "Sheetfile" "missing.kicad_sch"))', encoding="utf-8"
    )
    missing = build_import_review(root, source, "power-board", "kicad-10.0.5")
    assert missing.status == "NEEDS_WORK"
    assert any(item.disposition == "MISSING" for item in missing.files)


def test_changed_source_between_review_and_apply_stops_before_copy(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    source = _source(tmp_path)
    review = build_import_review(root, source, "power-board", "kicad-10.0.5")
    source.with_suffix(".kicad_sch").write_text("(kicad_sch (changed))", encoding="utf-8")
    with pytest.raises(ValueError, match="source changed"):
        apply_reviewed_import(
            root, source, "power-board", "kicad-10.0.5", Path(review.output_directory)
        )
    assert not (root / "projects/power-board").exists()


def test_changed_toolchain_catalog_stops_reviewed_import(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    source = _source(tmp_path)
    review = build_import_review(root, source, "power-board", "kicad-10.0.5")
    catalog = root / "catalog/toolchains.json"
    catalog.write_text(catalog.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="configuration changed"):
        apply_reviewed_import(
            root, source, "power-board", "kicad-10.0.5", Path(review.output_directory)
        )
    assert not (root / "projects/power-board").exists()


def test_reviewed_import_cli_rejects_changed_source(tmp_path: Path) -> None:
    root, _, _ = parity_workspace(tmp_path)
    source = _source(tmp_path)
    review = build_import_review(root, source, "power-board", "kicad-10.0.5")
    source.with_suffix(".kicad_pcb").write_text("(changed)", encoding="utf-8")
    result = subprocess.run(
        (
            sys.executable,
            "-I",
            "-m",
            "kicad_tooling.template",
            "import-project",
            "--root",
            str(root),
            "--source",
            str(source),
            "--project-id",
            "power-board",
            "--toolchain",
            "kicad-10.0.5",
            "--review-receipt",
            review.output_directory,
            "--format",
            "json",
        ),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "source changed" in result.stdout
    assert not (root / "projects/power-board").exists()


class _ImportReviewParity(McpParityHarness):
    async def _case_test_cli_mcp_import_review_parity(self) -> None:
        source = self.incoming.relative_to(self.root).as_posix()
        cli = await self.cli(
            "kicad_tooling.import_review",
            ImportReviewReport,
            "--source",
            source,
            "--project-id",
            "incoming",
            "--toolchain",
            "kicad-10.0.5",
            "--output",
            "build/import-review/cli",
        )
        arguments = {
            "source": source,
            "project_id": "incoming",
            "toolchain_id": "kicad-10.0.5",
            "view_id": "mcp",
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue((await client.call_tool("export_import_review", arguments)).is_error)
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(client, "export_import_review", ImportReviewReport, arguments)
            (self.base / "outside.kicad_pro").write_text("{}", encoding="utf-8")
            self.assertTrue(
                (
                    await client.call_tool(
                        "export_import_review",
                        {
                            **arguments,
                            "source": str(self.base / "outside.kicad_pro"),
                            "view_id": "outside",
                        },
                    )
                ).is_error
            )
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_text(encoding="utf-8"),
            (Path(mcp.output_directory) / "index.html").read_text(encoding="utf-8"),
        )
        cli_review = build_import_review(
            self.root,
            self.incoming,
            "incoming-cli",
            "kicad-10.0.5",
            Path("build/import-review/apply-cli"),
        )
        mcp_review = build_import_review(
            self.root,
            self.incoming,
            "incoming-mcp",
            "kicad-10.0.5",
            Path("build/import-review/apply-mcp"),
        )
        cli_applied = await self.cli(
            "kicad_tooling.template",
            ProjectImportReport,
            "import-project",
            "--source",
            source,
            "--project-id",
            "incoming-cli",
            "--toolchain",
            "kicad-10.0.5",
            "--review-receipt",
            Path(cli_review.output_directory).relative_to(self.root).as_posix(),
        )
        async with Client(create_server(self.root, allow_writes=True), mode="legacy") as client:
            mcp_applied = await self.call(
                client,
                "import_project",
                ProjectImportReport,
                {
                    "source": source,
                    "project_id": "incoming-mcp",
                    "toolchain_id": "kicad-10.0.5",
                    "review_receipt": Path(mcp_review.output_directory)
                    .relative_to(self.root)
                    .as_posix(),
                },
            )
        self.assertEqual(cli_applied.status, "PASS")
        self.assertEqual(mcp_applied.status, "PASS")
        self.assertEqual(cli_applied.copied_sha256, mcp_applied.copied_sha256)


def test_cli_mcp_import_review_parity() -> None:
    run_mcp_parity(_ImportReviewParity, "_case_test_cli_mcp_import_review_parity")
