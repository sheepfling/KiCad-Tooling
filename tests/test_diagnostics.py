"""New-engineer repair guidance against real importer and policy results."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.diagnostic_journal import DiagnosticJournal
from kicad_tooling.hwrepo.diagnostics import (
    bom_binding_findings,
    bom_findings,
    diagnose_import,
    diagnose_project,
    finding,
    format_text,
    native_findings,
    quote_argument,
    report,
    repository_guidance,
)
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    PcbValidationContract,
    ProjectManifest,
    ProjectTestContract,
    ValidationSummary,
)
from kicad_tooling.validate import hashes
from tests.support import initialize_git, reference_root


class DiagnosticTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="kicad-diagnostics-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_import_coaches_missing_sheet_without_copying_source(self) -> None:
        source = self.root / "legacy"
        source.mkdir()
        project = source / "legacy.kicad_pro"
        project.write_text("{}")
        (source / "legacy.kicad_sch").write_text('(property "Sheetfile" "missing.kicad_sch")')
        report = diagnose_import(reference_root(), project, "legacy-board", "kicad-10.0.5")
        self.assertEqual(report.status, "NEEDS_WORK")
        self.assertIn("Sheetfile", report.findings[0].action)
        self.assertFalse((reference_root() / "projects/legacy-board").exists())

        (source / "legacy.kicad_sch").write_text("(kicad_sch)")
        (source / "legacy.kicad_pcb").write_text("(kicad_pcb)")
        (source / "old.gbr").write_text("working export")
        fixed = diagnose_import(reference_root(), project, "legacy-board", "kicad-10.0.5")
        self.assertEqual(fixed.status, "PASS")
        self.assertEqual(fixed.findings[0].severity, "REVIEW")
        self.assertIn("generated export", fixed.findings[0].observed)
        self.assertFalse((reference_root() / "projects/legacy-board").exists())

    def test_import_preview_coaches_missing_3d_model_before_copy(self) -> None:
        source = self.root / "legacy-model"
        source.mkdir()
        project = source / "legacy-model.kicad_pro"
        project.write_text("{}", encoding="utf-8")
        (source / "legacy-model.kicad_pcb").write_text(
            '(kicad_pcb (footprint "Lib:Part" (property "Reference" "U1") '
            '(model "${KIPRJMOD}/models/Part.step")))', encoding="utf-8",
        )
        report = diagnose_import(reference_root(), project, "legacy-model", "kicad-10.0.5")
        self.assertEqual(report.status, "NEEDS_WORK")
        problem = next(item for item in report.findings if item.code == "CAD_PATH")
        self.assertIn("legacy-model.kicad_pcb", problem.location)
        self.assertIn("Part.step", problem.observed)
        self.assertIn("original source", problem.action)
        self.assertIn("kicad_tooling.template diagnose", report.next_command)
        self.assertFalse((reference_root() / "projects/legacy-model").exists())

        models = source / "models"
        models.mkdir()
        (models / "Part.step").write_text("authored model", encoding="utf-8")
        repaired = diagnose_import(reference_root(), project, "legacy-model", "kicad-10.0.5")
        self.assertEqual(repaired.status, "PASS", repaired.findings)
        self.assertIn("kicad_tooling.template import-project", repaired.next_command)

    def test_import_preview_checks_copied_library_without_blocking_excluded_cache(self) -> None:
        source = self.root / "local-library"
        source.mkdir()
        project = source / "local-library.kicad_pro"
        project.write_text("{}", encoding="utf-8")
        (source / "local-library.kicad_pcb").write_text("(kicad_pcb)", encoding="utf-8")
        (source / "fp-lib-table").write_text(
            '(fp_lib_table (lib (name "Local") (type "KiCad") '
            '(uri "${KIPRJMOD}/Local.pretty") (options "") (descr "")))',
            encoding="utf-8",
        )
        pretty = source / "Local.pretty"
        pretty.mkdir()
        footprint = pretty / "Part.kicad_mod"
        footprint.write_text('(footprint "Part")', encoding="utf-8")
        (pretty / "fp-info-cache").write_text("local cache", encoding="utf-8")
        valid = diagnose_import(reference_root(), project, "local-library", "kicad-10.0.5")
        self.assertEqual(valid.status, "PASS", valid.findings)
        self.assertFalse(any(row.code == "CAD_PATH" for row in valid.findings))
        footprint.write_text(
            '(footprint "Part" (model "${KIPRJMOD}/models/missing.step"))',
            encoding="utf-8",
        )
        broken = diagnose_import(reference_root(), project, "local-library", "kicad-10.0.5")
        self.assertEqual(broken.status, "NEEDS_WORK")
        self.assertTrue(any(row.code == "CAD_PATH" and "missing.step" in row.observed
                            for row in broken.findings))

    def test_real_portable_failure_names_dependency_and_repair(self) -> None:
        repository = self.root / "repository"
        shutil.copytree(reference_root(), repository, ignore=shutil.ignore_patterns(".git"))
        initialize_git(repository)
        board = repository / "examples/projects/controller/kicad/controller.kicad_pcb"
        board.write_text(board.read_text() + '\n(model "/Users/someone/Desktop/part.step")\n')
        result = diagnose_project(repository, "controller")
        paths = [row for row in result.findings if row.code == "CAD_PATH"]
        self.assertEqual(result.status, "NEEDS_WORK")
        self.assertEqual(len(paths), 1)
        self.assertIn("controller.kicad_pcb", paths[0].location)
        self.assertRegex(paths[0].location, r"controller\.kicad_pcb:\d+$")
        self.assertIn("declared shared library", paths[0].action)
        self.assertIn("machine-local dependency", paths[0].observed)

        manifest_path = repository / "examples/projects/controller/project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        contract = read_model(manifest_path.parent / manifest.checks, ProjectTestContract)
        self.assertIsInstance(contract.validation, PcbValidationContract)
        alternate = "tests/review-expectations.json"
        write_model(manifest_path.parent / alternate, contract.model_copy(update={
            "validation": contract.validation.model_copy(update={"components": {}, "nets": {}})
        }))
        write_model(manifest_path, manifest.model_copy(update={"checks": alternate}))
        relocated = diagnose_project(repository, "controller")
        empty = next(row for row in relocated.findings if row.code == "EMPTY_COMPONENT_CONTRACT")
        self.assertEqual(empty.location, f"examples/projects/controller/{alternate}")
        self.assertIn(empty.location, empty.action)
        native = self.root / "native"
        native.mkdir()
        write_model(native / "summary.json", ValidationSummary(
            timestamp_utc="2026-09-24T00:00:00+00:00",
            checked_commit="LOCAL_UNBOUND",
            project_id="controller",
            checks={
                "source_scope": CheckEvidence(
                    status="PASS", source_hashes=hashes(repository, load_config(
                        repository, "examples/projects/controller/project.json"
                    ).source_roots),
                ),
                "netlist": CheckEvidence(status="FAIL", error="component mismatch"),
            },
            status="FAIL",
            artifacts_sha256={},
        ))
        netlist_issue = next(row for row in native_findings(native, "controller", repository)
                             if row.code == "NATIVE_NETLIST")
        self.assertIn(empty.location, netlist_issue.action)

    def test_native_disabled_checks_and_bom_identifiers_have_distinct_actions(self) -> None:
        native = self.root / "native"
        native.mkdir()
        write_model(native / "summary.json", ValidationSummary(
            timestamp_utc="2026-09-24T00:00:00+00:00",
            checked_commit="LOCAL_UNBOUND",
            project_id="controller",
            checks={
                "source_scope": CheckEvidence(status="PASS", source_hashes={"fake": "0" * 64}),
                "erc": CheckEvidence(
                    status="FAIL", returncode=5,
                    error="Disabled-check inventory changed: ('single_global_label',)",
                ),
            },
            status="FAIL",
            artifacts_sha256={},
        ))
        (native / "erc.json").write_text(json.dumps({
            "sheets": [{"violations": [{"type": "pin_not_connected",
                                          "description": "Pin 3 on J1 is unconnected"}]}]
        }))
        issues = native_findings(native, "controller")
        self.assertEqual(len(issues), 1)
        self.assertIn("Schematic Setup", issues[0].action)
        self.assertIn("Do not change", issues[0].action)
        self.assertIn("pin_not_connected: Pin 3 on J1", issues[0].observed)
        current_source = native_findings(native, "controller", reference_root())
        self.assertEqual(current_source[0].code, "STALE_NATIVE_REPORT")
        wrong = native_findings(native, "some-other-board")
        self.assertEqual(wrong[0].code, "NATIVE_REPORT")

        bom = self.root / "bom.csv"
        with bom.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(("Reference", "Value", "Footprint", "PartID", "DNP"))
            writer.writerow(("R1", "1k", "R_Axial", "", ""))
            writer.writerow(("J1", "Header", "PinHeader", "not-in-catalog", ""))
            writer.writerow(("D1", "LED", "LED_THT", "training-generic-led-red-5mm", ""))
        items = bom_findings(reference_root(), bom)
        self.assertEqual([item.code for item in items], ["BOM_PART_ID", "BOM_TRAINING_PART"])
        self.assertIn("R1", items[0].observed)
        self.assertIn("schematic", items[0].action)
        self.assertIn("not-for-manufacture", items[1].observed)
        bom.write_text("Reference,Value,Footprint,PartID,DNP\nR2,1k\n")
        self.assertEqual(bom_findings(reference_root(), bom)[0].code, "BOM_INPUT")

    def test_bom_must_match_selected_project_native_netlist(self) -> None:
        native = self.root / "native"
        native.mkdir()
        netlist = native / "netlist.xml"
        netlist.write_text(
            '<export><components><comp ref="R1"><value>1k</value>'
            '<footprint>R_Axial</footprint></comp>'
            '<comp ref="R2"><value>2k</value><footprint>R_Axial</footprint></comp>'
            '<comp ref="LOGO1"><value>Logo</value><footprint>Graphic</footprint>'
            '<property name="exclude_from_bom"/></comp>'
            '<comp ref="D1"><value>LED</value><footprint>LED_THT</footprint>'
            '<property name="dnp"/></comp></components><nets/></export>'
        )
        config = load_config(reference_root(), "examples/projects/controller/project.json")
        write_model(native / "summary.json", ValidationSummary(
            timestamp_utc="2026-09-24T00:00:00+00:00",
            checked_commit="LOCAL_UNBOUND",
            project_id="controller",
            checks={"source_scope": CheckEvidence(
                status="PASS", source_hashes=hashes(reference_root(), config.source_roots)
            )},
            status="PASS",
            artifacts_sha256={"netlist.xml": hashlib.sha256(netlist.read_bytes()).hexdigest()},
        ))
        bom = self.root / "other-board-bom.csv"
        bom.write_text("Reference,Value,Footprint,PartID,DNP\nR1,1k,R_Axial,,\nR2,2k,R_Axial,,\n")
        self.assertEqual(bom_binding_findings(reference_root(), "controller", bom, native), [])
        bom.write_text("Reference,Value,Footprint,PartID,DNP\nR1,1k,R_Axial,,\n")
        incomplete = bom_binding_findings(reference_root(), "controller", bom, native)
        self.assertIn("R2", incomplete[0].observed)
        bom.write_text("Reference,Value,Footprint,PartID,DNP\nC1,100nF,C_0603,,\n")
        mismatch = bom_binding_findings(reference_root(), "controller", bom, native)
        self.assertEqual(mismatch[0].code, "BOM_BINDING")
        self.assertIn("C1", mismatch[0].observed)
        self.assertEqual(bom_binding_findings(reference_root(), "controller", bom, None)[0].code,
                         "BOM_BINDING")

    def test_cli_explains_import_in_text_and_json(self) -> None:
        source = self.root / "legacy"
        source.mkdir()
        project = source / "legacy.kicad_pro"
        project.write_text("{}")
        (source / "legacy.kicad_sch").write_text('(property "Sheetfile" "lost.kicad_sch")')
        command = (
            sys.executable, "-I", "-B", "-m", "kicad_tooling.template", "diagnose",
            "--root", str(reference_root()), "--source", str(project),
            "--project-id", "legacy-board", "--toolchain", "kicad-10.0.5",
        )
        text_log = self.root / "text-log"
        text_result = subprocess.run((*command, "--log-dir", str(text_log)),
                                     capture_output=True, text=True, check=False)
        self.assertEqual(text_result.returncode, 1)
        self.assertIn("Fix: Find the intended sheet", text_result.stdout)
        self.assertIn(str(text_log.resolve() / "events.log"), text_result.stdout)
        self.assertIn("import-preview done", text_result.stderr)
        self.assertIn("Missing schematic sheet", (text_log / "import-preview.json").read_text())
        self.assertEqual(json.loads((text_log / "run.json").read_text())["status"], "NEEDS_WORK")
        self.assertEqual(json.loads((text_log / "diagnosis.json").read_text())["run_directory"],
                         str(text_log.resolve()))
        json_log = self.root / "json-log"
        json_result = subprocess.run((*command, "--format", "json", "--log-dir", str(json_log)),
                                     capture_output=True, text=True, check=False)
        self.assertEqual(json_result.returncode, 1)
        self.assertEqual(json.loads(json_result.stdout)["run_directory"], str(json_log.resolve()))
        full_log = self.root / "full-log"
        full_result = subprocess.run((*command, "--detail", "full", "--log-dir", str(full_log)),
                                     capture_output=True, text=True, check=False)
        self.assertEqual(full_result.returncode, 1)
        self.assertIn("[BLOCKING] IMPORT", full_result.stdout)
        self.assertEqual((full_log / "diagnosis.txt").read_text().strip(),
                         full_result.stdout.strip())
        incompatible = subprocess.run((*command, "--format", "json", "--detail", "full"),
                                      capture_output=True, text=True, check=False)
        self.assertEqual(incompatible.returncode, 2)
        self.assertIn("JSON already includes every finding", incompatible.stderr)
        doctor_text = subprocess.run((sys.executable, "-I", "-B", "-m", "kicad_tooling.template", "doctor",
                                      "--root", str(reference_root()), "--format", "text"), capture_output=True,
                                     text=True, check=False)
        self.assertEqual(doctor_text.returncode, 0, doctor_text.stderr)
        self.assertIn("Template doctor: PASS", doctor_text.stdout)
        unbound_bom = subprocess.run((sys.executable, "-I", "-B", "-m", "kicad_tooling.template", "diagnose",
                                      "--project-id", "controller", "--bom", str(self.root / "bom.csv")),
                                     capture_output=True, text=True, check=False)
        self.assertEqual(unbound_bom.returncode, 2)
        self.assertIn("requires --native-report", unbound_bom.stderr)

    def test_crash_preserves_stage_log_and_traceback(self) -> None:
        from kicad_tooling.template import main

        source = self.root / "board.kicad_pro"
        source.write_text("{}")
        log = self.root / "crash-log"
        argv = ["kicad_tooling.template", "diagnose", "--root", str(reference_root()),
                "--source", str(source), "--project-id", "broken-board",
                "--toolchain", "kicad-10.0.5", "--log-dir", str(log)]
        stderr = io.StringIO()
        with patch.object(sys, "argv", argv), patch(
            "kicad_tooling.hwrepo.diagnostics.import_project", side_effect=RuntimeError("probe failure")
        ), redirect_stderr(stderr), redirect_stdout(io.StringIO()):
            self.assertEqual(main(), 2)
        self.assertIn("full traceback", stderr.getvalue())
        self.assertIn("[import-preview] ERROR", (log / "events.log").read_text())
        self.assertIn("RuntimeError: probe failure", (log / "error.txt").read_text())
        self.assertEqual(json.loads((log / "run.json").read_text())["status"], "ERROR")

    def test_default_log_is_ignored_and_custom_log_cannot_enter_source_tree(self) -> None:
        repository = self.root / "repository"
        shutil.copytree(reference_root(), repository, ignore=shutil.ignore_patterns(".git"))
        initialize_git(repository)
        journal = DiagnosticJournal(repository, "board")
        ignored = subprocess.run(
            ("git", "-C", str(repository), "check-ignore", "-q", str(journal.directory)),
            check=False,
        )
        self.assertEqual(ignored.returncode, 0)
        with self.assertRaisesRegex(ValueError, "under ignored build"):
            DiagnosticJournal(repository, "board", repository / "docs/diagnostic-output")
        self.assertFalse((repository / "docs/diagnostic-output").exists())

    def test_repeated_findings_are_grouped_but_retained_in_full(self) -> None:
        rows = [finding("BLOCKING", "CAD_PATH", f"board.kicad_pcb:{index}",
                        "machine-local dependency", "Move the asset into the project.",
                        "docs/workflow/IMPORT_WORKFLOW.md") for index in range(5)]
        result = report("board", "project", rows, "python -B -m kicad_tooling.template diagnose")
        formatted = format_text(result)
        self.assertIn("CAD_PATH (5 finding(s))", formatted)
        self.assertIn("... and 2 more in diagnosis.json", formatted)
        self.assertNotIn("board.kicad_pcb:4", formatted)
        self.assertEqual(len(result.findings), 5)
        full = format_text(result, "full")
        self.assertIn("CAD_PATH at board.kicad_pcb:4", full)
        self.assertIn("board.kicad_pcb:4", full)
        self.assertEqual(full.count("Move the asset into the project."), 5)

    def test_next_command_quotes_powershell_apostrophes(self) -> None:
        self.assertEqual(quote_argument("C:\\Users\\O'Connor\\board", windows=True),
                         "'C:\\Users\\O''Connor\\board'")

    def test_stale_native_report_requests_fresh_verification(self) -> None:
        repository = self.root / "repository"
        shutil.copytree(reference_root(), repository, ignore=shutil.ignore_patterns(".git"))
        initialize_git(repository)
        native = self.root / "stale-native"
        native.mkdir()
        write_model(native / "summary.json", ValidationSummary(
            timestamp_utc="2026-09-24T00:00:00+00:00",
            checked_commit="LOCAL_UNBOUND",
            project_id="controller",
            checks={"source_scope": CheckEvidence(
                status="PASS", source_hashes={"outdated-source": "0" * 64}
            )},
            status="PASS",
            artifacts_sha256={},
        ))
        result = diagnose_project(repository, "controller", native_report=native)
        self.assertIn("STALE_NATIVE_REPORT", {row.code for row in result.findings})
        self.assertIn("kicad_tooling.verify", result.next_command)
        self.assertIn("--depth native", result.next_command)
        self.assertNotIn("--native-report", result.next_command)

        bom = self.root / "bom.csv"
        bom.write_text("Reference,Value,Footprint,PartID,DNP\nR1,1k,R_Axial,,\n")
        with_bom = diagnose_project(repository, "controller", native_report=native, bom=bom)
        self.assertIsNotNone(with_bom.follow_up_command)
        self.assertIn("--native-report FRESH_NATIVE_DIR", with_bom.follow_up_command or "")
        self.assertIn(f"--bom {quote_argument(str(bom))}", with_bom.follow_up_command or "")
        self.assertIn("Follow-up command:", format_text(with_bom))

        summary_path = native / "summary.json"
        summary = read_model(summary_path, ValidationSummary)
        write_model(summary_path, summary.model_copy(update={"project_id": "another-board"}))
        wrong_project = diagnose_project(repository, "controller", native_report=native)
        self.assertIn("NATIVE_REPORT", {row.code for row in wrong_project.findings})
        self.assertIn("--depth native", wrong_project.next_command)
        self.assertNotIn("--native-report", wrong_project.next_command)

    def test_incomplete_backup_receives_specific_import_repair(self) -> None:
        source = self.root / "incomplete"
        source.mkdir()
        project = source / "backup.kicad_pro"
        project.write_text("{}")
        result = diagnose_import(reference_root(), project, "backup", "kicad-10.0.5")
        self.assertEqual(result.status, "NEEDS_WORK")
        self.assertIn("neither a matching schematic nor board", result.findings[0].action)

    def test_import_receipt_coaches_each_exclusion_class(self) -> None:
        source = self.root / "mixed"
        source.mkdir()
        project = source / "mixed.kicad_pro"
        project.write_text("{}")
        (source / "mixed.kicad_sch").write_text("(kicad_sch)")
        (source / "mixed.kicad_pcb").write_text("(kicad_pcb)")
        (source / "old.gbr").write_text("generated")
        (source / "mixed.kicad_prl").write_text("preference")
        (source / "vendor.zip").write_text("archive")
        (source / "other.kicad_pro").write_text("{}")
        (source / "orphan.kicad_sch").write_text("(kicad_sch)")
        nested = source / "nested"
        nested.mkdir()
        (nested / "nested.kicad_pro").write_text("{}")
        result = diagnose_import(reference_root(), project, "mixed", "kicad-10.0.5")
        self.assertEqual(result.status, "PASS")
        self.assertEqual(len(result.findings), 6)
        actions = "\n".join(row.action for row in result.findings)
        for repair in ("Regenerate", "caches", "authored documentation", "separate",
                       "unused backup"):
            self.assertIn(repair, actions)

    def test_path_policy_has_distinct_repairs_for_survey_causes(self) -> None:
        cases = (
            ("machine-local dependency '/Users/ee/model.step'", "portable path"),
            ("undocumented path variable '${OLD_KICAD_VAR}'", "pinned KiCad"),
            ("path case mismatch", "case-sensitive host"),
            ("missing dependency model.step", "intended asset"),
            ("missing embedded model kicad-embed://model.step", "intended asset"),
            ("invalid versioned KiCad library path", "pinned KiCad"),
            ("dependency is not in this project's required_inputs", "registered libraries/<id>/"),
            ("library directory has no inventoried inputs for this project", "registered libraries/<id>/"),
            ("library directory is outside this project's source_roots", "registered libraries/<id>/"),
            ("library directory exposes unlisted files", "registered libraries/<id>/"),
        )
        for observed, repair in cases:
            with self.subTest(observed=observed):
                row = repository_guidance(f"CAD_PATH: projects/board.kicad_pcb:12: {observed}")
                self.assertEqual(row.location, "projects/board.kicad_pcb:12")
                self.assertIn(repair, row.action)
        installed = repository_guidance(
            "CAD_PATH: projects/fp-lib-table:3: machine-local dependency "
            "'/usr/share/kicad/footprints/Package_LGA.pretty'", "10"
        )
        self.assertIn("${KICAD10_FOOTPRINT_DIR}", installed.action)
        self.assertIn("Do not copy standard KiCad libraries", installed.action)

    def test_failing_island_test_is_named_and_repairable(self) -> None:
        repository = self.root / "repository"
        shutil.copytree(reference_root(), repository, ignore=shutil.ignore_patterns(".git"))
        initialize_git(repository)
        probe = repository / "examples/projects/controller/tests/test_probe.py"
        probe.write_text(
            "import unittest\n"
            "class Probe(unittest.TestCase):\n"
            "    def test_requirement(self):\n"
            "        self.assertEqual(1, 2, 'connector contract changed')\n"
        )
        result = diagnose_project(repository, "controller")
        failing = next(row for row in result.findings if row.code == "PROJECT_TEST")
        self.assertEqual(result.status, "NEEDS_WORK")
        self.assertIn("project-controller", failing.location)
        self.assertIn("connector contract changed", failing.observed)
        self.assertIn("requirement", failing.action)


if __name__ == "__main__":
    unittest.main()
