"""Electrical CLI setup preserves review boundaries and reports useful next steps."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.ci import project_static_pipeline
from kicad_tooling.electrical import main as electrical_main
from kicad_tooling.hwrepo.cli_output import summary
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.diagnostics import portable_findings
from kicad_tooling.hwrepo.electrical import policy_issues, selected_config, simulation_cases
from kicad_tooling.hwrepo.electrical_doctor import electrical_checks
from kicad_tooling.hwrepo.electrical_runner import analyze, format_report
from kicad_tooling.hwrepo.electrical_setup import capture_inputs, initialize
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    ElectricalCheck,
    ElectricalSuiteReport,
    ProjectTestContract,
)
from kicad_tooling.template import main as template_main
from kicad_tooling.verify import verify
from tests import test_verify
from tests.support import TEMPLATE_ROOT, reference_root
from tests.test_electrical import ISLAND, NA, PROJECT, install_fixture


class ElectricalSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="electrical-setup-")
        self.addCleanup(temporary.cleanup)
        self.root = (Path(temporary.name) / "repository").resolve()
        shutil.copytree(reference_root(), self.root)
        self.native = self.root / ISLAND / "tests/contract.json"
        self.sidecar = self.native.with_name("electrical.json")

    def command(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (sys.executable, "-I", "-B", "-m", "kicad_tooling.electrical", "--root", str(self.root),
             "--project", PROJECT, *args), text=True, capture_output=True, check=False,
        )

    def test_initialization_connects_pending_requirements_and_preserves_native_expectations(self) -> None:
        before = read_model(self.native, ProjectTestContract)
        os.chmod(self.native, 0o644)
        report = initialize(self.root, PROJECT)
        after = read_model(self.native, ProjectTestContract)
        self.assertEqual(after.model_copy(update={"electrical": None}), before)
        self.assertEqual(self.native.stat().st_mode & 0o777, 0o644)
        self.assertEqual(report.status, "CREATED")
        contract = read_model(self.sidecar, ElectricalAnalysisContract)
        self.assertEqual(contract.ngspice_version, "UNREVIEWED")
        self.assertEqual([contract.grounding.mode, contract.power.mode, contract.high_frequency.mode], ["pending"] * 3)
        self.assertEqual(simulation_cases(contract), ())
        self.assertIn("Pending", " ".join(policy_issues(self.root, selected_config(self.root, PROJECT))))
        with patch("kicad_tooling.hwrepo.electrical_runner.capture") as native, patch("kicad_tooling.hwrepo.electrical_runner.run_case") as spice:
            result = analyze(self.root, PROJECT)
        native.assert_not_called()
        spice.assert_not_called()
        self.assertEqual(result.status, "FAIL")
        self.assertEqual([c.status for c in result.checks], ["NOT_CONFIGURED"] * 3)
        portable = project_static_pipeline(self.root, (PROJECT,))
        self.assertEqual(portable.status, "FAIL")
        # The diagnostic points at the authoring source and provides a CLI remedy.
        findings = portable_findings(self.root, PROJECT, portable_report=portable)
        self.assertNotIn("ELECTRICAL_NOT_CONFIGURED", {row.code for row in findings})
        electrical = next(row for row in findings if row.code == "ELECTRICAL_SETUP")
        self.assertIn("electrical", electrical.location)
        self.assertIn("doctor", electrical.action)

    def test_repeated_init_and_existing_sidecar_never_overwrite(self) -> None:
        initialize(self.root, PROJECT, "47")
        before = (self.native.read_bytes(), self.sidecar.read_bytes())
        with self.assertRaisesRegex(ValueError, "already configured"):
            initialize(self.root, PROJECT)
        self.assertEqual((self.native.read_bytes(), self.sidecar.read_bytes()), before)
        contract = read_model(self.native, ProjectTestContract).model_copy(update={"electrical": None})
        write_model(self.native, contract)
        before_native = self.native.read_bytes()
        with self.assertRaisesRegex(ValueError, "overwrite"):
            initialize(self.root, PROJECT)
        self.assertEqual(self.native.read_bytes(), before_native)
        self.assertEqual(self.sidecar.read_bytes(), before[1])

    def test_failed_pointer_write_rolls_back_only_its_own_sidecar(self) -> None:
        before = self.native.read_bytes()
        with (patch("kicad_tooling.hwrepo.electrical_setup.os.replace", side_effect=OSError("write blocked")),
              self.assertRaisesRegex(OSError, "write blocked")):
            initialize(self.root, PROJECT)
        self.assertEqual(self.native.read_bytes(), before)
        self.assertFalse(self.sidecar.exists())
        self.assertEqual(list(self.native.parent.glob(".electrical-*")), [])

    def test_sidecar_symlink_cannot_write_outside_the_island(self) -> None:
        outside = self.root.parent / "outside.json"
        outside.write_text("preserve")
        self.sidecar.symlink_to(outside)
        with self.assertRaises(ValueError):
            initialize(self.root, PROJECT)
        self.assertEqual(outside.read_text(), "preserve")

    def test_capture_records_current_hashes_without_refreshing_reviewed_contract(self) -> None:
        contract = install_fixture(self.root)
        before = self.sidecar.read_bytes()
        deck = self.root / simulation_cases(contract)[0].deck
        deck.write_text(deck.read_text() + "\n")
        report = capture_inputs(self.root, PROJECT)
        self.assertEqual(report.status, "UNREVIEWED")
        self.assertFalse(report.build_authorized)
        self.assertEqual(len(report.model_sha256), 2)
        self.assertEqual(report.model_sha256[deck.relative_to(self.root).as_posix()], digest(deck))
        self.assertEqual(self.sidecar.read_bytes(), before)
        self.assertTrue(policy_issues(self.root, selected_config(self.root, PROJECT)))
        receipt = Path(report.run_directory) / "inputs.json"
        self.assertTrue(receipt.is_relative_to(self.root / "build"))
        self.assertEqual(json.loads(receipt.read_text())["status"], "UNREVIEWED")
        self.assertNotEqual(capture_inputs(self.root, PROJECT).run_directory, report.run_directory)

    def test_capture_accepts_explicit_model_before_contract_and_rejects_unowned_paths(self) -> None:
        deck = self.native.with_name("model.cir")
        deck.write_text("Synthetic\nR1 in 0 1k\n.end\n")
        name = deck.relative_to(self.root).as_posix()
        report = capture_inputs(self.root, PROJECT, (name, name))
        self.assertEqual(report.model_sha256, {name: digest(deck)})
        self.assertFalse(self.sidecar.exists())
        self.assertEqual(capture_inputs(self.root, PROJECT).model_sha256, {})
        for path in ("../outside.cir", "README.md", "build/model.cir", "examples/projects/other/model.cir"):
            with self.subTest(path=path), self.assertRaises((OSError, ValueError)):
                capture_inputs(self.root, PROJECT, (path,))
        with self.assertRaises(ValueError):
            capture_inputs(self.root, PROJECT, (name,), self.root / "templates/receipt")

    def test_cli_reports_setup_status_counts_and_refuses_unused_arguments(self) -> None:
        created = self.command("--init", "--ngspice-version", "47", "--format", "json")
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertEqual(json.loads(created.stdout)["status"], "CREATED")
        capture = self.command("--capture-inputs")
        self.assertEqual(capture.returncode, 0, capture.stderr)
        self.assertIn("UNREVIEWED", capture.stdout)
        self.assertIn("0 model files", capture.stdout)
        self.assertIn("inputs.json", capture.stdout)
        for args in (("--init", "--output", "build/ignored"), ("--model", "x"),
                     ("--ngspice-version", "47"), ("--init", "--runner", "local"),
                     ("--capture-inputs", "--ngspice", "other"), ("--format", "json", "--detail", "full")):
            with self.subTest(args=args):
                result = self.command(*args)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("error:", result.stderr)

    def test_doctor_coaches_missing_pending_and_unreviewed_configuration(self) -> None:
        self.assertIn("--init", electrical_checks(self.root, PROJECT, "ngspice")[0].next_action)
        self.assertEqual(electrical_checks(self.root, None, "ngspice")[0].status, "FAIL")
        initialize(self.root, PROJECT)
        with patch("kicad_tooling.hwrepo.electrical_doctor.run_command") as command:
            checks = electrical_checks(self.root, PROJECT, "ngspice")
        command.assert_not_called()
        self.assertEqual([row.status for row in checks], ["FAIL", "FAIL"])
        self.assertEqual(checks[-1].observed, "UNREVIEWED")

    def test_doctor_accepts_exact_multiline_banner_and_rejects_missing_wrong_or_error(self) -> None:
        install_fixture(self.root)
        for banner, code, error, status in (
            ("******\n** ngspice-47 : Circuit level simulation program\n******", 0, None, "PASS"),
            ("ngspice-470", 0, None, "FAIL"), ("ngspice-46", 0, None, "FAIL"),
            ("ngspice-47", 1, None, "FAIL"), ("", 127, "not found", "FAIL"),
        ):
            evidence = CommandEvidence(argv=("ngspice",), started_utc="fixture", returncode=code, stdout=banner, error=error)
            with self.subTest(banner=banner, code=code), patch("kicad_tooling.hwrepo.electrical_doctor.run_command", return_value=evidence):
                check = electrical_checks(self.root, PROJECT, "selected-ngspice")[-1]
                self.assertEqual(check.status, status)
                if status == "FAIL":
                    self.assertIn("--ngspice", check.next_action)

    def test_grounding_only_contract_needs_no_simulator(self) -> None:
        contract = install_fixture(self.root).model_copy(update={"power": NA, "high_frequency": NA})
        write_model(self.sidecar, contract)
        with patch("kicad_tooling.hwrepo.electrical_doctor.run_command") as command:
            checks = electrical_checks(self.root, PROJECT, "missing")
        command.assert_not_called()
        self.assertTrue(all(row.status == "PASS" for row in checks))
        self.assertFalse(checks[-1].required)
        self.assertEqual(checks[-1].observed, "NOT_REQUIRED")

    def test_electrical_preflight_stops_combined_run_before_native_work(self) -> None:
        install_fixture(self.root)
        evidence = CommandEvidence(argv=("missing",), started_utc="fixture", returncode=127, error="not found")
        with (test_verify.VerifyTests.runner_environment("10.0.0"),
              patch("kicad_tooling.hwrepo.electrical_doctor.run_command", return_value=evidence),
              patch("kicad_tooling.verify.check_all") as native):
            report = verify(self.root, PROJECT, depth="electrical", runner="local", ngspice="missing")
        native.assert_not_called()
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(report.doctor.electrical_requested)
        self.assertIn("ngspice", report.model_dump_json())

    def test_doctor_cli_routes_electrical_and_simulator_options(self) -> None:
        from kicad_tooling.hwrepo.models import TemplateDoctorReport

        report = TemplateDoctorReport(native_requested=True, electrical_requested=True, checks=(), status="PASS", next_actions=())
        with (patch("kicad_tooling.template.doctor", return_value=report) as doctor,
              patch.object(sys, "argv", ["kicad_tooling.template", "doctor", "--electrical", "--project-id", PROJECT,
                                          "--runner", "container", "--ngspice", "custom"]),
              patch("sys.stdout", new_callable=StringIO) as output):
            self.assertEqual(template_main(), 0)
        self.assertTrue(json.loads(output.getvalue())["electrical_requested"])
        self.assertEqual(doctor.call_args.kwargs["ngspice"], "custom")
        self.assertTrue(doctor.call_args.kwargs["electrical"])

    def test_human_output_has_identity_failure_and_receipt_with_full_json_unchanged(self) -> None:
        report = ElectricalAnalysisReport(
            project_id=PROJECT, status="FAIL", run_directory="build/electrical/controller-run",
            checks=tuple(ElectricalCheck(id=f"measure-{n}", status="FAIL", detail=f"Voltage limit {n} exceeded") for n in range(7)),
        )
        suite = ElectricalSuiteReport(status="FAIL", projects=(report,))
        output = summary("Electrical suite", suite)
        self.assertIn("controller: FAIL (build/electrical/controller-run)", output)
        self.assertIn("Voltage limit 0 exceeded", output)
        self.assertNotIn("Voltage limit 6 exceeded", output)
        self.assertIn("--format json", output)
        self.assertIn("7 need attention", format_report(report))
        self.assertIn("measure-6", format_report(report, "full"))
        self.assertEqual(len(json.loads(suite.model_dump_json())["projects"][0]["checks"]), 7)
        with (patch("kicad_tooling.electrical.analyze", return_value=report),
              patch.object(sys, "argv", ["kicad_tooling.electrical", "--root", str(self.root), "--project", PROJECT, "--detail", "full"]),
              patch("sys.stdout", new_callable=StringIO) as stream):
            self.assertEqual(electrical_main(), 1)
        self.assertIn("measure-6", stream.getvalue())

    def test_standalone_example_is_valid_schema_but_has_no_approved_binding(self) -> None:
        contract = read_model(TEMPLATE_ROOT / "templates/electrical/contract.example.json", ElectricalAnalysisContract)
        self.assertEqual(contract.project_id, "example-board")
        self.assertEqual(len(simulation_cases(contract)), 4)
        for case in simulation_cases(contract):
            self.assertEqual(set(case.source_sha256.values()), {"0" * 64})
            self.assertEqual(set(case.model_sha256.values()), {"0" * 64})
            self.assertTrue((TEMPLATE_ROOT / "templates/electrical" / Path(case.deck).name).is_file())

    def test_hosted_electrical_workflow_retains_failure_artifacts(self) -> None:
        workflow = (TEMPLATE_ROOT / ".github/workflows/electrical-analysis.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertIn("contents: read", workflow)
        # Template revisions may dispatch the shared Python lane or its older CLI
        # composition. Behavioral simulator/CI enforcement is tested in tooling.
        self.assertIn("kicad_tooling.", workflow)
        self.assertIn("if: always()", workflow)
        self.assertIn("build/electrical/", workflow)
        self.assertIn("build/electrical-charts/", workflow)
        self.assertIn("-r requirements-tooling.txt", workflow)
        self.assertNotIn("continue-on-error", workflow)
        self.assertNotIn("run: ${{ inputs.", workflow)


if __name__ == "__main__":
    unittest.main()
