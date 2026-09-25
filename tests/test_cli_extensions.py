"""Regression checks for variant-bound exports and guarded foreign PCB conversion."""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from itertools import pairwise
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.exports import (
    command_arguments,
    require_declared_variant,
    review_artifacts_valid,
)
from kicad_tooling.hwrepo.foreign_pcb import ForeignPcbReport, convert_pcb
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    EnvironmentCheck,
    ReleaseArtifactKind,
    ReleaseExportSettings,
    ReleaseVariant,
    TemplateDoctorReport,
)
from kicad_tooling.hwrepo.product import load_repository, validate_product
from kicad_tooling.hwrepo.release import (
    expected_board_population,
    selected_board_variants,
    verify_board_population,
)
from kicad_tooling.hwrepo.releasing import artifact_kind
from kicad_tooling.hwrepo.three_d import _specifications
from tests.support import reference_root


class ExportExtensionTests(unittest.TestCase):
    def test_typed_settings_roundtrip_and_reject_invalid_formats(self) -> None:
        settings = ReleaseExportSettings(
            gerber_layers=("F.Cu", "B.Cu", "Edge.Cuts"),
            assembly_variant="Pilot A", supplier_formats=("odb", "ipc2581", "ipcd356"),
        )
        self.assertEqual(ReleaseExportSettings.model_validate_json(settings.model_dump_json()), settings)
        for patch_values in (
            {"supplier_formats": ["odb", "odb"]},
            {"supplier_formats": ["unknown"]},
            {"assembly_variant": ""},
            {"surprise": True},
        ):
            with self.subTest(patch_values=patch_values), self.assertRaises(ValidationError):
                ReleaseExportSettings.model_validate({**settings.model_dump(), **patch_values})

    def test_all_population_exports_use_one_variant_and_physical_reports_do_not(self) -> None:
        settings = ReleaseExportSettings(
            gerber_layers=("F.Cu", "B.Cu", "Edge.Cuts"),
            supplier_formats=("odb", "ipc2581", "ipcd356"),
        )
        commands = command_arguments(settings, Path("/work/board"), Path("/output"), "Pilot A")
        self.assertEqual(set(commands), {
            "gerbers", "drill", "position", "bom", "schematic_pdf", "pcb_pdf",
            "board_stats", "odb", "ipc2581", "ipcd356",
        })
        for name in ("gerbers", "position", "bom", "schematic_pdf", "pcb_pdf", "odb", "ipc2581"):
            with self.subTest(name=name):
                self.assertEqual(commands[name].count("--variant"), 1)
                self.assertEqual(commands[name][commands[name].index("--variant") + 1], "Pilot A")
        for name in ("drill", "board_stats", "ipcd356"):
            self.assertNotIn("--variant", commands[name])
        for _, _, argv in _specifications("projects/board/kicad/board.kicad_pcb", "Pilot A"):
            self.assertIn(("--variant", "Pilot A"), tuple(pairwise(argv)))

    def test_unknown_variant_is_rejected_before_kicad_can_silently_use_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "board.kicad_pro"
            project.write_text(json.dumps({"schematic": {"variants": [{"name": "Pilot A"}]}}))
            require_declared_variant(project, "Pilot A")
            with self.assertRaisesRegex(ValueError, "not declared"):
                require_declared_variant(project, "Pilot B")
            project.write_text(json.dumps({"schematic": {"variants": []}}))
            with self.assertRaisesRegex(ValueError, "not declared"):
                require_declared_variant(project, "Pilot A")
            project.write_text(json.dumps({"schematic": {"variants": ["Pilot A", "pilot a"]}}))
            with self.assertRaisesRegex(ValueError, "duplicate names"):
                require_declared_variant(project, "Pilot A")

    def test_release_artifacts_identify_review_packet_and_bom(self) -> None:
        output = Path("/release")
        self.assertEqual(artifact_kind(output / "exports/board/review/schematic.pdf", output),
                         ReleaseArtifactKind.SCHEMATIC_EXPORT)
        self.assertEqual(artifact_kind(output / "exports/board/review/pcb.pdf", output),
                         ReleaseArtifactKind.PCB_EXPORT)
        self.assertEqual(artifact_kind(output / "exports/board/assembly/bom.csv", output),
                         ReleaseArtifactKind.BOM)

    def test_review_outputs_require_real_pdf_json_and_supplier_archives(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "review").mkdir()
            (output / "fabrication").mkdir()
            (output / "review/schematic.pdf").write_bytes(b"%PDF-1.5\n")
            (output / "review/pcb.pdf").write_bytes(b"%PDF-1.5\n")
            (output / "review/board-stats.json").write_text("{}")
            settings = ReleaseExportSettings(gerber_layers=("F.Cu",), supplier_formats=("odb",))
            self.assertFalse(review_artifacts_valid(output, settings))
            import zipfile

            with zipfile.ZipFile(output / "fabrication/board.odb.zip", "w") as archive:
                archive.writestr("manifest", "sample")
            self.assertTrue(review_artifacts_valid(output, settings))
            (output / "review/board-stats.json").write_text("not JSON")
            self.assertFalse(review_artifacts_valid(output, settings))

    def test_product_board_variant_mapping_is_scoped_and_conflicts_fail(self) -> None:
        repository = load_repository(reference_root())
        product = repository.products[0]
        standard = product.variants[0].model_copy(update={
            "board_variants": {"arduino-uno-status-led": "Pilot A"},
        })
        other = product.variants[1].model_copy(update={
            "board_variants": {"arduino-uno-status-led": "Pilot B"},
        })
        edited = product.model_copy(update={"variants": (standard, other, *product.variants[2:])})
        self.assertFalse(validate_product(reference_root(), edited, repository.parts,
                                          repository.interfaces, repository.projects))
        selections = (
            ReleaseVariant(product=edited.id, product_revision=edited.revision,
                           variant=standard.id, variant_revision=standard.revision),
            ReleaseVariant(product=edited.id, product_revision=edited.revision,
                           variant=other.id, variant_revision=other.revision),
        )
        self.assertEqual(selected_board_variants((edited,), selections[:1],
                                                  ("arduino-uno-status-led",)),
                         {"arduino-uno-status-led": "Pilot A"})
        with self.assertRaisesRegex(ValueError, "Conflicting KiCad assembly variants"):
            selected_board_variants((edited,), selections, ("arduino-uno-status-led",))
        excluded = standard.model_copy(update={"board_variants": {"not-a-board": "Pilot A"}})
        invalid = edited.model_copy(update={"variants": (excluded, *edited.variants[1:])})
        self.assertIn("VARIANT_BOARD", {issue.code for issue in validate_product(
            reference_root(), invalid, repository.parts, repository.interfaces, repository.projects,
        )})

    def test_product_population_must_match_native_fitted_part_id_rows(self) -> None:
        product = load_repository(reference_root()).products[0]
        standard = product.variants[0].model_copy(update={"exclude": ("UNO.R1",)})
        edited = product.model_copy(update={"variants": (standard, *product.variants[1:])})
        expected = expected_board_population(edited, standard.id, "arduino-uno-status-led")
        self.assertIsNotNone(expected)
        assert expected is not None
        self.assertEqual(set(expected), {"J1", "D1"})
        choice = ReleaseVariant(product=edited.id, product_revision=edited.revision,
                                variant=standard.id, variant_revision=standard.revision)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bom.csv"

            def write(rows: dict[str, str]) -> None:
                with path.open("w", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(("Reference", "Value", "Footprint", "PartID", "DNP"))
                    for reference, part_id in rows.items():
                        writer.writerow((reference, "", "", part_id, ""))

            write(expected)
            verify_board_population((edited,), (choice,), "arduino-uno-status-led", path)
            write({**expected, "R1": "training-generic-resistor-1k-th"})
            with self.assertRaisesRegex(ValueError, "extra=\\['R1'\\]"):
                verify_board_population((edited,), (choice,), "arduino-uno-status-led", path)
            write({**expected, "J1": "wrong-part"})
            with self.assertRaisesRegex(ValueError, "changed_part_ids=\\['J1'\\]"):
                verify_board_population((edited,), (choice,), "arduino-uno-status-led", path)


class ForeignPcbConversionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="foreign-pcb-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repo"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git", "build"))
        self.source = Path(temporary.name) / "vendor layout.brd"
        self.source.write_text("foreign board fixture")

    @staticmethod
    def doctor_report() -> TemplateDoctorReport:
        return TemplateDoctorReport(native_requested=True, status="PASS", checks=(
            EnvironmentCheck(id="native-runner", required=True, status="PASS",
                             expected="exact", observed="local", next_action="ready"),
        ))

    def test_success_keeps_source_and_repository_untouched_until_reviewed_import(self) -> None:
        before = self.source.read_bytes()

        def run(_root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
            self.assertEqual(timeout, 600)
            if argv[-1] == "version":
                return CommandEvidence(argv=argv, started_utc="now", returncode=0, stdout="10.0.5\n")
            board = Path(argv[argv.index("--output") + 1])
            board.write_text("(kicad_pcb (version 20260206))")
            Path(argv[argv.index("--report-file") + 1]).write_text(
                '{"source_format":"eagle","layer_mapping":{},"errors":[],"warnings":[]}'
            )
            return CommandEvidence(argv=argv, started_utc="now", returncode=0)

        with (patch("kicad_tooling.hwrepo.foreign_pcb.doctor", return_value=self.doctor_report()),
              patch("kicad_tooling.hwrepo.foreign_pcb.cli_executable", return_value="/fake/kicad-cli"),
              patch("kicad_tooling.hwrepo.foreign_pcb.run_command", side_effect=run)):
            report = convert_pcb(self.root, self.source, "vendor-board", "kicad-10.0.5")
        self.assertEqual(report.status, "PASS", report.error)
        self.assertEqual(report.runner, "local")
        self.assertEqual(self.source.read_bytes(), before)
        self.assertFalse((self.root / "projects/vendor-board").exists())
        self.assertEqual(report.import_preview.status, "PASS")
        self.assertTrue(report.import_preview.dry_run)
        self.assertIn("import-project", report.next_command)
        receipt = Path(report.run_directory)
        self.assertTrue((receipt / "conversion.json").is_file())
        self.assertTrue((receipt / "convert-command.json").is_file())
        self.assertTrue((receipt / "kicad-import-report.json").is_file())
        self.assertEqual(read_model(receipt / "conversion.json", ForeignPcbReport), report)

    def test_invalid_source_returns_json_failure_with_receipt(self) -> None:
        command = (sys.executable, "-B", "-m", "kicad_tooling.template", "convert-pcb",
                   "--root", str(self.root), "--project-id", "vendor-board",
                   "--toolchain", "kicad-10.0.5", "--source", str(self.source.with_suffix(".missing")),
                   "--format", "json")
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1, result.stderr)
        report = ForeignPcbReport.model_validate_json(result.stdout)
        self.assertEqual(report.status, "FAIL")
        self.assertTrue((Path(report.run_directory) / "events.log").is_file())
        self.assertFalse((self.root / "projects/vendor-board").exists())

    def test_invalid_project_id_still_returns_typed_json_and_a_receipt(self) -> None:
        for project_id in ("bad/id", "with space", ""):
            with self.subTest(project_id=project_id):
                result = subprocess.run((
                    sys.executable, "-B", "-m", "kicad_tooling.template", "convert-pcb",
                    "--root", str(self.root), "--project-id", project_id,
                    "--toolchain", "kicad-10.0.5", "--source", str(self.source),
                    "--format", "json",
                ), capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 1, result.stderr)
                report = ForeignPcbReport.model_validate_json(result.stdout)
                self.assertEqual(report.status, "FAIL")
                self.assertEqual(report.project_id, project_id)
                self.assertIn("Project ID", report.error)
                self.assertTrue((Path(report.run_directory) / "events.log").is_file())
        self.assertFalse((self.root / "projects/vendor-board").exists())

    def test_invalid_toolchain_id_still_returns_typed_json_and_a_receipt(self) -> None:
        result = subprocess.run((
            sys.executable, "-B", "-m", "kicad_tooling.template", "convert-pcb",
            "--root", str(self.root), "--project-id", "vendor-board",
            "--toolchain", "bad/id", "--source", str(self.source),
            "--format", "json",
        ), capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1, result.stderr)
        report = ForeignPcbReport.model_validate_json(result.stdout)
        self.assertEqual(report.status, "FAIL")
        self.assertEqual(report.toolchain_id, "bad/id")
        self.assertIn("Toolchain ID", report.error)
        self.assertTrue((Path(report.run_directory) / "events.log").is_file())


if __name__ == "__main__":
    unittest.main()
