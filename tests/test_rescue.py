"""Local rescue never converts a partial island inspection into CI acceptance."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.diagnostic_journal import DiagnosticJournal
from kicad_tooling.hwrepo.diagnostics import diagnose_project
from kicad_tooling.hwrepo.rescue import rescue_project
from kicad_tooling.template import main as template_main
from tests.support import initialize_git, reference_root


class LocalRescueTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="kicad-rescue-")
        self.addCleanup(temporary.cleanup)
        self.root = (Path(temporary.name) / "repository").resolve()
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git"))
        initialize_git(self.root)

    def command(self, *extra: str, output_format: str = "json") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (sys.executable, "-I", "-B", "-m", "kicad_tooling.template", "rescue",
             "--root", str(self.root), "--project-id", "controller",
             "--format", output_format, *extra),
            cwd=self.root, capture_output=True, text=True, check=False,
        )

    def source_snapshot(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file() and path.relative_to(self.root).parts[0] not in {".git", "build"}
        }

    def test_unrelated_malformed_manifest_does_not_block_selected_local_coaching(self) -> None:
        peer = self.root / "examples/projects/arduino-uno-status-led/project.json"
        peer.write_text("{malformed", encoding="utf-8")
        normal = diagnose_project(self.root, "controller")
        self.assertEqual(normal.status, "NEEDS_WORK")
        self.assertEqual(normal.findings[0].code, "DISCOVERY")
        before = self.source_snapshot()
        command = self.command()
        self.assertEqual(command.returncode, 1, command.stderr)
        result = json.loads(command.stdout)
        self.assertEqual(result["status"], "UNVERIFIED_GLOBAL")
        self.assertEqual(result["local_inspection"], "CLEAR")
        self.assertEqual(result["selected_manifest"],
                         "examples/projects/controller/project.json")
        self.assertFalse(result["build_authorized"])
        self.assertFalse(result["ci_eligible"])
        self.assertFalse(result["release_eligible"])
        self.assertEqual(result["findings"], [])
        self.assertEqual(before, self.source_snapshot())
        receipt = Path(result["run_directory"])
        self.assertTrue(receipt.is_relative_to(self.root / "build"))
        self.assertEqual(json.loads((receipt / "run.json").read_text())["status"],
                         "UNVERIFIED_GLOBAL")
        self.assertEqual(json.loads((receipt / "diagnosis.json").read_text())["lane"],
                         "LOCAL_PROJECT_RESCUE")
        self.assertIn("selected-island", command.stderr)

    def test_rescue_does_not_call_global_registry_even_when_it_is_valid(self) -> None:
        with patch("kicad_tooling.hwrepo.discovery.load_registry", side_effect=AssertionError(
            "Global registry must not be loaded",
        )):
            report = rescue_project(self.root, "controller", DiagnosticJournal(
                self.root, "controller",
            ))
        self.assertEqual(report.local_inspection, "CLEAR")
        self.assertEqual(report.status, "UNVERIFIED_GLOBAL")

    def test_selected_manifest_parse_error_is_a_local_finding(self) -> None:
        manifest = self.root / "examples/projects/controller/project.json"
        manifest.write_text("{bad", encoding="utf-8")
        command = self.command("--detail", "full", output_format="text")
        self.assertEqual(command.returncode, 1)
        self.assertIn("SELECTED_MANIFEST", command.stdout)
        self.assertIn("UNVERIFIED_GLOBAL", command.stdout)
        self.assertIn("not eligible for CI", command.stdout)

    def test_selected_shared_root_cannot_borrow_another_project_private_directory(self) -> None:
        manifest = self.root / "examples/projects/controller/project.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["shared_source_roots"] = ["examples/projects/arduino-uno-status-led/kicad"]
        data["shared_inputs"] = [
            "examples/projects/arduino-uno-status-led/kicad/arduino-uno-status-led.kicad_sch"
        ]
        manifest.write_text(json.dumps(data), encoding="utf-8")
        command = self.command()
        self.assertEqual(command.returncode, 1)
        result = json.loads(command.stdout)
        self.assertEqual(result["local_inspection"], "NEEDS_REPAIR")
        self.assertIn("SELECTED_SHARED_ROOT", {row["code"] for row in result["findings"]})
        self.assertFalse((Path(result["run_directory"]) / "portable.json").exists())

    def test_unsafe_or_ambiguous_selection_is_rejected_before_manifest_parse(self) -> None:
        for project_id in ("../other", "team/controller"):
            with self.subTest(project_id=project_id):
                report = rescue_project(self.root, project_id, DiagnosticJournal(
                    self.root, project_id,
                ))
                self.assertEqual(report.local_inspection, "NEEDS_REPAIR")
                self.assertEqual(report.findings[0].code, "RESCUE_SELECTION")
        duplicate = self.root / "projects/controller"
        shutil.copytree(self.root / "examples/projects/controller", duplicate)
        report = rescue_project(self.root, "controller", DiagnosticJournal(
            self.root, "controller",
        ))
        self.assertIn("ambiguous", report.findings[0].observed)

    def test_nested_project_directory_is_not_discovered(self) -> None:
        controller = self.root / "examples/projects/controller"
        nested = self.root / "examples/projects/team/controller"
        nested.parent.mkdir()
        controller.rename(nested)
        report = rescue_project(self.root, "controller", DiagnosticJournal(
            self.root, "controller",
        ))
        self.assertEqual(report.findings[0].code, "RESCUE_SELECTION")
        self.assertIn("No project.json", report.findings[0].observed)

    def test_linked_selected_manifest_is_rejected_before_reading_target(self) -> None:
        manifest = self.root / "examples/projects/controller/project.json"
        outside = self.root.parent / "outside-project.json"
        outside.write_text("{broken and outside}", encoding="utf-8")
        manifest.unlink()
        manifest.symlink_to(outside)
        result = json.loads(self.command().stdout)
        self.assertEqual(result["local_inspection"], "NEEDS_REPAIR")
        self.assertEqual(result["findings"][0]["code"], "RESCUE_SELECTION")
        self.assertIn("Linked repository path", result["findings"][0]["observed"])

    def test_unexpected_tool_error_keeps_traceback_in_ignored_receipt(self) -> None:
        argv = [
            "kicad_tooling.template", "rescue", "--root", str(self.root),
            "--project-id", "controller",
        ]
        with (
            patch.object(sys, "argv", argv),
            patch("kicad_tooling.template.rescue_project", side_effect=RuntimeError("coach bug")),
            redirect_stderr(StringIO()) as stderr,
        ):
            self.assertEqual(template_main(), 2)
        self.assertIn("Full traceback", stderr.getvalue())
        receipts = sorted((self.root / "build/diagnostics").iterdir())
        self.assertEqual(len(receipts), 1)
        self.assertIn("coach bug", (receipts[0] / "error.txt").read_text())
        self.assertEqual(json.loads((receipts[0] / "run.json").read_text())["status"],
                         "ERROR")

    def test_missing_selected_input_is_reported_without_global_verification(self) -> None:
        source = self.root / "examples/projects/controller/kicad/Pilot.kicad_sym"
        source.unlink()
        result = json.loads(self.command().stdout)
        self.assertEqual(result["status"], "UNVERIFIED_GLOBAL")
        self.assertEqual(result["local_inspection"], "NEEDS_REPAIR")
        self.assertIn("SELECTED_INPUT_MISSING", {row["code"] for row in result["findings"]})


if __name__ == "__main__":
    unittest.main()
