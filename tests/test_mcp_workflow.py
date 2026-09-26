"""Exercise MCP workflow policy with real fixtures and explicitly synthetic native evidence."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo import mcp_workflow as workflow
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.models import (
    DEFAULT_THREE_D_VIEWS,
    CommandEvidence,
    EnvironmentCheck,
    ReleaseClass,
    ReleaseExportReport,
    ReleaseStatus,
    TemplateDoctorReport,
)
from tests import test_contract_coach, test_release_evidence, test_visualize
from tests.support import initialize_git, reference_root


def runner_report(runner: str = "local") -> TemplateDoctorReport:
    return TemplateDoctorReport(
        native_requested=True, status="PASS", checks=(EnvironmentCheck(
            id="native-runner", required=True, status="PASS", expected="Synthetic runner",
            observed=runner, next_action="Synthetic test evidence only",
        ),),
    )


class McpWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="mcp-workflow-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repository"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git", "build"))
        initialize_git(self.root)
        subprocess.run(("git", "-C", str(self.root), "-c", "user.name=Test fixture", "-c",
                        "user.email=fixture@example.invalid", "commit", "-qm", "Synthetic fixture"),
                       check=True, capture_output=True)

    def release_fixture(self):
        fixture = test_release_evidence.ReleaseEvidenceTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def contract_fixture(self):
        fixture = test_contract_coach.ContractCoachTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def test_diagnosis_runs_selected_checks_and_preserves_full_receipt(self) -> None:
        report = workflow.diagnose_project(self.root, "controller")
        self.assertEqual(report.status, "PASS", report.findings)
        receipt = Path(report.run_directory)
        self.assertTrue(receipt.is_relative_to(self.root / "build/diagnostics"))
        self.assertTrue((receipt / "portable.json").is_file())
        self.assertEqual(json.loads((receipt / "run.json").read_text())["status"], "PASS")
        self.assertFalse(report.build_authorized)
        second = workflow.diagnose_project(self.root, "controller")
        self.assertNotEqual(report.run_directory, second.run_directory)

    def test_import_diagnosis_retains_preview_without_importing(self) -> None:
        source = self.root / "examples/projects/controller/kicad/controller.kicad_pro"
        report = workflow.diagnose_import(self.root, source, "incoming", "kicad-10.0.0")
        self.assertEqual(report.status, "PASS", report.findings)
        self.assertTrue((Path(report.run_directory) / "import-preview.json").is_file())
        self.assertFalse((self.root / "projects/incoming").exists())

    def test_rescue_stays_unverified_when_peer_manifest_is_malformed(self) -> None:
        (self.root / "examples/projects/passive-signal-reference/project.json").write_text("{bad")
        report = workflow.rescue_project(self.root, "controller")
        self.assertEqual(report.status, "UNVERIFIED_GLOBAL")
        self.assertEqual(report.local_inspection, "CLEAR")
        self.assertFalse(report.ci_eligible)
        self.assertFalse(report.release_eligible)
        self.assertTrue((Path(report.run_directory) / "diagnosis.json").is_file())

    def test_receipt_parent_links_and_artifact_scope_fail_before_execution(self) -> None:
        with patch("kicad_tooling.hwrepo.mcp_workflow.diagnostics.diagnose_project") as execute:
            for path in ("README.md", "../outside.json", str(self.root / "README.md")):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    workflow.diagnose_project(self.root, "controller", path)
            with self.assertRaisesRegex(ValueError, "requires"):
                workflow.diagnose_project(self.root, "controller", bom="build/bom.csv")
            execute.assert_not_called()
        if hasattr(Path, "symlink_to"):
            outside = self.root.parent / "outside"
            outside.mkdir()
            try:
                (self.root / "build").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Directory symlinks unavailable")
            with self.assertRaisesRegex(ValueError, "Linked"):
                workflow.diagnose_project(self.root, "controller")
            self.assertEqual(list(outside.iterdir()), [])

    def test_diagnostic_crash_is_recorded_and_propagated(self) -> None:
        with (patch("kicad_tooling.hwrepo.mcp_workflow.diagnostics.diagnose_project",
                    side_effect=RuntimeError("Synthetic crash")),
              self.assertRaisesRegex(RuntimeError, "Synthetic crash")):
            workflow.diagnose_project(self.root, "controller")
        receipt = next((self.root / "build/diagnostics").iterdir())
        self.assertIn("Synthetic crash", (receipt / "error.txt").read_text())
        self.assertEqual(json.loads((receipt / "run.json").read_text())["status"], "ERROR")

    def test_scope_uses_real_selection_and_does_not_recurse_into_full_gate(self) -> None:
        report = workflow.check_scope(self.root, project_ids=("controller",))
        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.report.projects, ("controller",))
        self.assertTrue((Path(report.run_directory) / "scope.json").is_file())
        with patch("kicad_tooling.hwrepo.mcp_workflow.static_pipeline", return_value=report.report) as gate:
            workflow.check_scope(self.root)
            gate.assert_called_once_with(self.root, None, workers=1)
        with self.assertRaisesRegex(ValueError, "Unknown product"):
            workflow.check_scope(self.root, product_ids=("missing-product",))

    def test_contract_inspection_is_unreviewed_and_stale_evidence_is_blocked(self) -> None:
        fixture = self.contract_fixture()
        path = fixture.native.relative_to(fixture.root).as_posix() + "/summary.json"
        report = workflow.inspect_contract(fixture.root, fixture.project_id, path)
        self.assertEqual(report.status, "READY_FOR_REVIEW", report.issues)
        self.assertEqual(report.review_state, "UNREVIEWED")
        self.assertFalse(report.electrical_coverage)
        schematic = fixture.root / "examples/projects/controller/kicad/controller.kicad_sch"
        schematic.write_text(schematic.read_text() + "\n")
        stale = workflow.inspect_contract(fixture.root, fixture.project_id, path)
        self.assertEqual(stale.status, "BLOCKED")
        self.assertIn("source", " ".join(stale.issues))

    def test_contract_capture_uses_fixed_runner_and_preserves_contract(self) -> None:
        fixture = self.contract_fixture()
        contract = fixture.root / "examples/projects/controller/tests/contract.json"
        before = contract.read_bytes()
        runner = test_contract_coach.FakeRunner("10.0.0")
        with patch("kicad_tooling.hwrepo.mcp_workflow.contract_coach.LocalNetlistRunner", return_value=runner) as create:
            report = workflow.capture_contract(fixture.root, fixture.project_id, "local")
        create.assert_called_once_with("kicad-cli")
        self.assertEqual(report.status, "READY_FOR_REVIEW", report.issues)
        self.assertTrue((Path(report.receipt_dir) / "report.json").is_file())
        self.assertEqual(contract.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "Unknown native runner"):
            workflow.capture_contract(fixture.root, fixture.project_id, "shell")

    def test_native_summary_sibling_symlink_is_rejected_before_read(self) -> None:
        fixture = self.contract_fixture()
        path = fixture.native / "netlist.xml"
        outside = fixture.root.parent / "private.xml"
        outside.write_text("private")
        path.unlink()
        try:
            path.symlink_to(outside)
        except OSError:
            self.skipTest("Symlinks unavailable")
        with self.assertRaisesRegex(ValueError, "Linked"):
            workflow.inspect_contract(fixture.root, fixture.project_id,
                                      (fixture.native / "summary.json").relative_to(fixture.root).as_posix())

    def test_prepare_review_reuses_real_candidate_gate_with_synthetic_native_evidence(self) -> None:
        fixture = self.release_fixture()

        def copy_native(_root, _project, output, _cli, _dependencies, export_only=False):
            self.assertFalse(export_only)
            shutil.copytree(fixture.native_path.parent, output)

        with (patch("kicad_tooling.hwrepo.mcp_workflow.doctor", return_value=runner_report()),
              patch("kicad_tooling.hwrepo.mcp_workflow.cli_executable", return_value="kicad-cli"),
              patch("kicad_tooling.hwrepo.releasing.run_native", side_effect=copy_native)):
            report = workflow.prepare_review(fixture.root, fixture.project_id, "mcp-review", "local")
        self.assertEqual(report.release_class, ReleaseClass.ENGINEERING_REVIEW)
        self.assertEqual(report.status, ReleaseStatus.CANDIDATE)
        self.assertIsNone(report.approval)
        self.assertEqual(workflow.check_release(fixture.root, "build/releases/mcp-review/manifest.json").status,
                         "PASS")
        with self.assertRaisesRegex(ValueError, "already exists"):
            workflow.prepare_review(fixture.root, fixture.project_id, "mcp-review")
        (fixture.root / "README.md").write_text("Changed source\n")
        with self.assertRaisesRegex(ValueError, "clean checkout"):
            workflow.prepare_review(fixture.root, fixture.project_id, "dirty-review")

    def test_container_prepare_captures_progress_and_reads_retained_manifest(self) -> None:
        fixture = self.release_fixture()

        def run(root, argv, timeout):
            self.assertIn("kicad_tooling.release", argv)
            self.assertIn("engineering_review", argv)
            self.assertNotIn("--cli", argv)
            output = root / "build/releases/container-review"
            output.mkdir(parents=True)
            write_model(output / "manifest.json", fixture.manifest.model_copy(update={
                "release_id": "container-review",
            }))
            return CommandEvidence(argv=argv, started_utc="2026-01-01T00:00:00Z", returncode=0,
                                   stdout="Pip progress is not JSON\n")

        with (patch("kicad_tooling.hwrepo.mcp_workflow.doctor", return_value=runner_report("container")),
              patch("kicad_tooling.hwrepo.mcp_workflow.run_command", side_effect=run)):
            result = workflow.prepare_review(fixture.root, fixture.project_id, "container-review", "container")
        self.assertEqual(result, fixture.manifest.model_copy(update={"release_id": "container-review"}))
        receipt = read_model(fixture.root / "build/releases/container-review.command.json", CommandEvidence)
        self.assertIn("not JSON", receipt.stdout)

    def test_package_roundtrip_keeps_paths_controlled_and_refuses_overwrites(self) -> None:
        fixture = self.release_fixture()
        package = workflow.package_release(fixture.root, fixture.manifest_name, "review-package")
        self.assertEqual(package.status, "PASS")
        path = "build/packages/review-package.zip"
        self.assertEqual(Path(package.package), fixture.root / path)
        self.assertEqual(workflow.verify_package(fixture.root, path).status, "PASS")
        self.assertEqual(workflow.restore_package(fixture.root, path, "review-copy").status, "PASS")
        self.assertTrue((fixture.root / "build/restores/review-copy/.git").is_dir())
        with self.assertRaisesRegex(ValueError, "already exists"):
            workflow.package_release(fixture.root, fixture.manifest_name, "review-package")
        with self.assertRaisesRegex(ValueError, "already exists"):
            workflow.restore_package(fixture.root, path, "review-copy")
        for identifier in ("../escape", "/tmp/outside", "bad/id"):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                workflow.package_release(fixture.root, fixture.manifest_name, identifier)
        (fixture.root / "README.md").write_text("Changed source\n")
        self.assertEqual(workflow.check_release(fixture.root, fixture.manifest_name).status, "FAIL")
        with self.assertRaisesRegex(ValueError, "not ready"):
            workflow.package_release(fixture.root, fixture.manifest_name, "stale-package")

    def test_export_checks_settings_clean_source_and_fresh_paths(self) -> None:
        with patch("kicad_tooling.hwrepo.mcp_workflow.selected_cli") as runner:
            with self.assertRaisesRegex(ValueError, "release_exports"):
                workflow.export_project(self.root, "controller", "missing-settings")
            (self.root / "README.md").write_text("Changed\n")
            with self.assertRaisesRegex(ValueError, "clean checkout"):
                workflow.export_project(self.root, "arduino-uno-status-led", "dirty")
            runner.assert_not_called()

    def test_export_executes_real_exporter_with_explicit_synthetic_native_outputs(self) -> None:
        def execute(argv, root, output, name):
            if name == "gerbers":
                (output / "fabrication/board.gbr").write_text("Synthetic Gerber")
            elif name == "drill":
                (output / "fabrication/board.drl").write_text("Synthetic drill")
            elif name == "position":
                (output / "assembly/positions.csv").write_text("Ref,PosX,PosY\nR1,0,0\n")
            elif name == "bom":
                (output / "assembly/bom.csv").write_text(
                    "Reference,Value,Footprint,PartID,DNP\n"
                    f"R1,1k,Resistor_SMD:R_0805_2012Metric,{part_id},\n")
            elif name in {"schematic_pdf", "pcb_pdf"}:
                (output / "review" / ("schematic.pdf" if name == "schematic_pdf" else "pcb.pdf")).write_bytes(
                    b"%PDF-1.5\nSynthetic review packet\n")
            elif name == "board_stats":
                (output / "review/board-stats.json").write_text("{}\n")
            return CommandEvidence(argv=argv, started_utc="2026-01-01T00:00:00Z", returncode=0,
                                   stdout="10.0.5\n" if name == "version" else "")

        # Read the real catalog identity rather than inventing accepted sourcing data.
        catalog = json.loads((self.root / "catalog/parts.json").read_text())
        part_id = catalog["parts"][0]["id"]

        with (patch("kicad_tooling.hwrepo.mcp_workflow.doctor", return_value=runner_report()),
              patch("kicad_tooling.hwrepo.mcp_workflow.cli_executable", return_value="kicad-cli"),
              patch("kicad_tooling.hwrepo.exports.execute", side_effect=execute)):
            report = workflow.export_project(self.root, "arduino-uno-status-led", "local-export", "local")
        self.assertIsInstance(report, ReleaseExportReport)
        self.assertEqual(report.status, "PASS")
        self.assertIn("assembly/purchasing-bom.csv", report.artifacts_sha256)
        self.assertTrue((self.root / "build/exports/local-export/files/exports.json").is_file())

    def test_generate_product_views_include_bom_and_refuse_reuse(self) -> None:
        result = workflow.generate_views(
            self.root, "product-review", product_ids=("status-indicator-system",),
        )
        self.assertEqual(result.status, "PASS")
        self.assertFalse(result.build_authorized)
        self.assertEqual(result.directory, "build/views/product-review")
        self.assertTrue(any("bom" in name.lower() for name in result.files), result.files)
        self.assertTrue(all((self.root / name).is_file() for name in result.files))
        with self.assertRaisesRegex(ValueError, "already exists"):
            workflow.generate_views(self.root, "product-review")


    def test_subprocess_failure_preserves_output_without_polluting_protocol(self) -> None:
        output = self.root / "build/command-test.json"
        captured = StringIO()
        with (redirect_stdout(captured), redirect_stderr(captured),
              self.assertRaisesRegex(ValueError, "build/command-test.json")):
            workflow.captured_command(self.root, (
                sys.executable, "-c",
                "import sys; print('child stdout'); print('child stderr', file=sys.stderr); sys.exit(7)",
            ), output, 30)
        self.assertEqual(captured.getvalue(), "")
        receipt = read_model(output, CommandEvidence)
        self.assertEqual(receipt.returncode, 7)
        self.assertIn("child stdout", receipt.stdout)
        self.assertIn("child stderr", receipt.stderr)
        with patch("kicad_tooling.hwrepo.mcp_workflow.run_command") as run:
            with self.assertRaisesRegex(ValueError, "already exists"):
                workflow.captured_command(self.root, (sys.executable, "--version"), output, 30)
            run.assert_not_called()

    def test_container_dependency_symlink_fails_before_any_export_write(self) -> None:
        outside = self.root.parent / "external-deps"
        outside.mkdir()
        (self.root / "build").mkdir()
        try:
            (self.root / "build/release-deps").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Directory symlinks unavailable")
        with (patch("kicad_tooling.hwrepo.mcp_workflow.selected_cli", return_value=None),
              patch("kicad_tooling.hwrepo.mcp_workflow.run_command") as run,
              self.assertRaisesRegex(ValueError, "Linked")):
            workflow.export_project(self.root, "arduino-uno-status-led", "linked-deps", "container")
        run.assert_not_called()
        self.assertFalse((self.root / "build/exports").exists())
        self.assertEqual(list(outside.iterdir()), [])


    def test_3d_export_rejects_linked_output_before_native_dispatch(self) -> None:
        external = self.root.parent / "external-3d"
        external.mkdir()
        (self.root / "build").mkdir()
        try:
            (self.root / "build/3d").symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest("Directory symlinks unavailable")
        with (patch("kicad_tooling.hwrepo.three_d.generate") as generate,
              self.assertRaisesRegex(ValueError, "Linked")):
            workflow.export_3d(self.root, "arduino-uno-status-led", "escaped")
        generate.assert_not_called()
        self.assertEqual(list(external.iterdir()), [])

    def test_3d_export_source_mutation_keeps_failure_and_receipt(self) -> None:
        board = self.root / test_visualize.BOARD
        original = board.read_bytes()
        payloads = {f"{name}.png": test_visualize.PNG for name in DEFAULT_THREE_D_VIEWS}
        payloads.update({"board.step": test_visualize.STEP, "board.glb": test_visualize.GLB})

        def native(_root, output, _config, _selected, _cli, args, timeout=300):
            if args == ("version",):
                return test_visualize.evidence(args, stdout="10.0.5\n")
            filename = Path(args[args.index("-o") + 1]).name
            (output / filename).write_bytes(payloads[filename])
            if filename == "top.png":
                board.write_bytes(original + b"\n")
            return test_visualize.evidence(args)

        with (patch("kicad_tooling.hwrepo.three_d.doctor", return_value=test_visualize.passing_doctor()),
              patch("kicad_tooling.hwrepo.three_d._run_kicad", side_effect=native)):
            report = workflow.export_3d(self.root, test_visualize.PROJECT, "stale-source", "local")
        self.assertEqual(report.status, "FAIL")
        self.assertIn("source changed", report.error)
        self.assertFalse(report.build_authorized)
        self.assertTrue((Path(report.run_directory) / "visualization.json").is_file())



if __name__ == "__main__":
    unittest.main()
