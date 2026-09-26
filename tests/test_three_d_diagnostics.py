"""Static PCB model findings join the existing diagnostic repair queue."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.diagnostic_journal import DiagnosticJournal
from kicad_tooling.hwrepo.diagnostics import diagnose_project
from kicad_tooling.hwrepo.model_inventory import ModelInventoryReport
from kicad_tooling.hwrepo.models import ProjectKind, ProjectManifest, ProjectTestContract
from tests.support import initialize_git, reference_root


class ThreeDDiagnosticTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="kicad-model-diagnosis-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repository"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git", "build"))
        initialize_git(self.root)
        self.island = self.root / "examples/projects/controller"
        self.board = self.island / "kicad/controller.kicad_pcb"
        self.manifest = self.island / "project.json"

    def board_source(self, model: str | None = None) -> None:
        assignment = "" if model is None else f' (model "{model}")'
        self.board.write_text(
            '(kicad_pcb\n  (footprint "Lib:Part" (property "Reference" "U1")'
            + assignment
            + ")\n)\n",
            encoding="utf-8",
        )

    def test_missing_models_are_review_findings_and_do_not_fail_portable_diagnosis(self) -> None:
        self.board_source()
        original = self.board.read_bytes()
        journal = DiagnosticJournal(self.root, "controller")
        with (
            patch(
                "kicad_tooling.hwrepo.three_d.doctor",
                side_effect=AssertionError("native runner started"),
            ),
            patch(
                "kicad_tooling.hwrepo.three_d.generate",
                side_effect=AssertionError("3D export started"),
            ),
        ):
            result = diagnose_project(self.root, "controller", journal=journal)
        self.assertEqual(result.status, "PASS", result.findings)
        findings = [item for item in result.findings if item.code == "MODEL_UNASSIGNED"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "REVIEW")
        self.assertIn("U1", findings[0].observed)
        self.assertIn("controller.kicad_pcb:", findings[0].location)
        self.assertFalse(result.build_authorized)
        self.assertIn("kicad_tooling.verify", result.next_command)
        self.assertEqual(self.board.read_bytes(), original)
        retained = read_model(journal.directory / "models.json", ModelInventoryReport)
        self.assertEqual(retained.status, "REVIEW")
        self.assertEqual(retained.findings, tuple(findings))
        self.assertIn(
            "model-inventory", (journal.directory / "events.log").read_text(encoding="utf-8")
        )

    def test_declared_assigned_model_has_no_model_repair_findings(self) -> None:
        self.board_source("${KIPRJMOD}/Part.step")
        model = self.island / "kicad/Part.step"
        model.write_text("authored model source", encoding="utf-8")
        manifest = read_model(self.manifest, ProjectManifest)
        write_model(
            self.manifest,
            manifest.model_copy(
                update={
                    "required_inputs": (*manifest.required_inputs, "kicad/Part.step"),
                }
            ),
        )
        original = {path: path.read_bytes() for path in (self.board, model, self.manifest)}
        result = diagnose_project(self.root, "controller")
        self.assertEqual(result.status, "PASS", result.findings)
        self.assertFalse(any(item.code.startswith("MODEL_") for item in result.findings))
        self.assertFalse(result.build_authorized)
        self.assertEqual({path: path.read_bytes() for path in original}, original)

    def test_missing_model_file_blocks_the_same_repair_queue(self) -> None:
        self.board_source("${KIPRJMOD}/missing.step")
        original = self.board.read_bytes()
        result = diagnose_project(self.root, "controller")
        self.assertEqual(result.status, "NEEDS_WORK")
        finding = next(item for item in result.findings if item.code == "MODEL_PATH")
        self.assertEqual(finding.severity, "BLOCKING")
        self.assertIn("missing.step", finding.observed)
        self.assertIn("reviewed model", finding.action)
        self.assertTrue(any(item.code == "CAD_PATH" for item in result.findings))
        self.assertIn("kicad_tooling.template diagnose", result.next_command)
        self.assertEqual(self.board.read_bytes(), original)

    def test_non_pcb_diagnosis_does_not_attempt_model_inspection(self) -> None:
        with patch(
            "kicad_tooling.hwrepo.diagnostics.inspect_models",
            side_effect=AssertionError("not a PCB"),
        ):
            result = diagnose_project(self.root, "passive-signal-reference")
        self.assertEqual(result.status, "PASS", result.findings)
        self.assertFalse(any(item.code.startswith("MODEL_") for item in result.findings))

    def test_pcb_only_keeps_scope_warning_and_model_review(self) -> None:
        self.board_source()
        manifest = read_model(self.manifest, ProjectManifest)
        write_model(self.manifest, manifest.model_copy(update={"kind": ProjectKind.PCB_ONLY}))
        contract = read_model(
            self.root / "templates/project-tests/pcb_only.json", ProjectTestContract
        )
        write_model(self.island / "tests/contract.json", contract)
        result = diagnose_project(self.root, "controller")
        self.assertTrue(any(item.code == "PCB_ONLY_SCOPE" for item in result.findings))
        model = next(item for item in result.findings if item.code == "MODEL_UNASSIGNED")
        self.assertEqual(model.severity, "REVIEW")
        self.assertFalse(result.build_authorized)

    def test_model_read_error_preserves_other_diagnostic_findings(self) -> None:
        with patch(
            "kicad_tooling.hwrepo.diagnostics.inspect_models",
            side_effect=ValueError("Linked board path"),
        ):
            result = diagnose_project(self.root, "controller")
        self.assertEqual(result.status, "NEEDS_WORK")
        failure = next(item for item in result.findings if item.code == "MODEL_INVENTORY")
        self.assertEqual(failure.severity, "BLOCKING")
        self.assertIn("Linked board path", failure.observed)
        self.assertTrue(any(item.code == "PART_ID_SCOPE" for item in result.findings))
        self.assertFalse(any(item.code == "DISCOVERY" for item in result.findings))


if __name__ == "__main__":
    unittest.main()
