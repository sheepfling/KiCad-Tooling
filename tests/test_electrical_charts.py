"""Chart exports consume only hashed saved evidence and preserve numeric waveforms."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.electrical_charts import build_charts, build_suite
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    ElectricalAnalysisReport,
    ElectricalChartsReport,
    ElectricalChartsSuiteReport,
    ElectricalSuiteReport,
)
from tests.support import reference_root
from tests.test_electrical import PROJECT, install_fixture


class ElectricalChartsTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="electrical-charts-")
        self.addCleanup(temporary.cleanup)
        self.root = (Path(temporary.name) / "repository").resolve()
        shutil.copytree(reference_root(), self.root)
        self.contract = install_fixture(self.root)
        self.source = self.root / "build/electrical/controller-saved"
        self.source.mkdir(parents=True)
        write_model(self.source / "requirements.json", self.contract)

    def raw(
        self,
        name: str,
        names: tuple[tuple[str, str], ...],
        points: tuple[tuple[complex, ...], ...],
        *,
        complex_mode: bool = False,
    ) -> None:
        directory = self.source / name
        directory.mkdir()
        lines = [
            "Title: saved test waveform",
            f"Flags: {'complex' if complex_mode else 'real'}",
            f"No. Variables: {len(names)}",
            f"No. Points: {len(points)}",
            "Variables:",
        ]
        lines.extend(f"{index}\t{label}\t{unit}" for index, (label, unit) in enumerate(names))
        lines.append("Values:")
        for index, values in enumerate(points):
            lines.append(str(index))
            lines.extend(
                f"{value.real:.17g},{value.imag:.17g}" if complex_mode else f"{value.real:.17g}"
                for value in values
            )
        (directory / "waveforms.raw").write_text("\n".join(lines) + "\n")

    def complete(self) -> ElectricalAnalysisReport:
        self.raw(
            "startup",
            (("time", "time"), ("i(value0)", "current")),
            ((0j, 0j), (0.001 + 0j, 4.9 + 0j), (0.005 + 0j, 0.05 + 0j)),
        )
        self.raw(
            "steady-state",
            (
                ("time", "time"),
                ("i(value0)", "current"),
                ("value1", "power"),
                ("v(value2)", "voltage"),
            ),
            (
                (0j, 0j, 0j, 0j),
                (0.004 + 0j, 0.05 + 0j, 0.25 + 0j, 4.95 + 0j),
                (0.005 + 0j, 0.05 + 0j, 0.25 + 0j, 4.95 + 0j),
            ),
        )
        self.raw(
            "passband",
            (
                ("frequency", "frequency"),
                ("value0", "decibel"),
                ("v(in)", "voltage"),
                ("v(out)", "voltage"),
            ),
            (
                (1000 + 0j, -0.001 + 0j, 1 + 0j, 1 - 0.001j),
                (1000000 + 0j, -0.002 + 0j, 1 + 0j, 1 - 0.002j),
                (1000000000 + 0j, -3 + 0j, 1 + 0j, 0.7 - 0.7j),
            ),
            complex_mode=True,
        )
        self.raw(
            "edges",
            (("time", "time"), ("v(value0)", "voltage")),
            ((0j, 0j), (0.000001 + 0j, 1 + 0j), (0.000003 + 0j, 1 + 0j)),
        )
        artifacts = {
            path.relative_to(self.source).as_posix(): digest(path)
            for path in self.source.rglob("*")
            if path.is_file()
        }
        report = ElectricalAnalysisReport(
            project_id=PROJECT,
            status="PASS",
            run_directory=str(self.source),
            artifacts_sha256=artifacts,
            checks=(),
        )
        write_model(self.source / "electrical.json", report)
        return report

    def test_exports_all_cases_and_full_precision_complex_csv(self) -> None:
        self.complete()
        before = (self.source / "electrical.json").read_bytes()
        result = build_charts(self.root, self.source)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(
            {item.id for item in result.cases}, {"startup", "steady-state", "passband", "edges"}
        )
        self.assertTrue(all(item.status == "PASS" for item in result.cases))
        output = Path(result.run_directory)
        self.assertTrue(output.is_relative_to(self.root / "build"))
        self.assertEqual(read_model(output / "charts.json", ElectricalChartsReport), result)
        for case in result.cases:
            assert case.csv and case.png and case.svg
            self.assertTrue((output / case.png).stat().st_size > 1000)
            self.assertTrue((output / case.svg).stat().st_size > 1000)
            self.assertEqual(result.artifacts_sha256[case.csv], digest(output / case.csv))
        with (output / "passband.csv").open(newline="") as stream:
            rows = list(csv.reader(stream))
        self.assertIn("v(out).real [voltage]", rows[0])
        self.assertIn("v(out).imag [voltage]", rows[0])
        self.assertEqual(float(rows[1][0]), 1000)
        self.assertEqual(float(rows[1][-1]), -0.001)
        self.assertTrue((output / "grounding.csv").is_file())
        self.assertTrue((output / "power.csv").is_file())
        self.assertEqual((self.source / "electrical.json").read_bytes(), before)

    def test_changed_or_unrecorded_waveform_cannot_be_plotted(self) -> None:
        self.complete()
        raw = self.source / "startup/waveforms.raw"
        raw.write_text(raw.read_text().replace("4.9000000000000004", "9.9000000000000004"))
        if "9.9000000000000004" not in raw.read_text():
            raw.write_text(raw.read_text() + "\n")
        with patch("kicad_tooling.hwrepo.electrical_charts.render_case") as renderer:
            result = build_charts(self.root, self.source)
        self.assertEqual(result.status, "FAIL")
        startup = next(item for item in result.cases if item.id == "startup")
        self.assertEqual(startup.status, "FAIL")
        self.assertIn("changed", startup.detail)
        # The tampered case never reaches the renderer.
        self.assertEqual(renderer.call_count, 3)
        self.assertIsNone(startup.png)

    def test_missing_waveform_is_partial_and_suites_are_accepted(self) -> None:
        report = self.complete()
        (self.source / "edges/waveforms.raw").unlink()
        result = build_charts(self.root, self.source)
        self.assertEqual(result.status, "FAIL")  # Recorded but missing is tampering.
        (self.source / "edges/waveforms.raw").write_text("partial data")
        artifacts = dict(report.artifacts_sha256)
        artifacts.pop("edges/waveforms.raw")
        write_model(
            self.source / "electrical.json",
            report.model_copy(update={"artifacts_sha256": artifacts, "status": "FAIL"}),
        )
        (self.source / "edges/waveforms.raw").unlink()
        partial = build_charts(self.root, self.source)
        self.assertEqual(partial.status, "PARTIAL")
        suite = ElectricalSuiteReport(
            status="FAIL",
            projects=(read_model(self.source / "electrical.json", ElectricalAnalysisReport),),
        )
        suite_path = self.root / "build/electrical-suite.json"
        write_model(suite_path, suite)
        batch = build_suite(self.root, suite_path)
        self.assertEqual(batch.status, "PARTIAL")
        self.assertEqual(
            read_model(Path(batch.run_directory) / "suite.json", ElectricalChartsSuiteReport), batch
        )

    def test_source_mutation_during_render_rejects_output_report(self) -> None:
        self.complete()
        from kicad_tooling.hwrepo.electrical_plot import render_case

        raw = self.source / "startup/waveforms.raw"

        def change_after_render(data, case, png, svg) -> None:
            render_case(data, case, png, svg)
            if case.id == "startup":
                raw.write_text(raw.read_text() + "\n")

        with (
            patch(
                "kicad_tooling.hwrepo.electrical_charts.render_case",
                side_effect=change_after_render,
            ),
            self.assertRaisesRegex(ValueError, "changed or is missing"),
        ):
            build_charts(self.root, self.source)

    def test_cli_exports_existing_receipt_as_machine_json(self) -> None:
        self.complete()
        command = subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.electrical_charts",
                "--root",
                str(self.root),
                "--receipt",
                "build/electrical/controller-saved",
                "--format",
                "json",
            ),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertEqual(json.loads(command.stdout)["status"], "PASS")

    def test_suite_rejects_a_changed_analysis_report(self) -> None:
        report = self.complete()
        suite_path = self.root / "build/electrical-suite.json"
        write_model(suite_path, ElectricalSuiteReport(status="PASS", projects=(report,)))
        write_model(self.source / "electrical.json", report.model_copy(update={"status": "FAIL"}))
        with self.assertRaisesRegex(ValueError, "disagree"):
            build_suite(self.root, suite_path)

    def test_receipts_outside_build_are_rejected(self) -> None:
        self.complete()
        with self.assertRaisesRegex(ValueError, "under this repository"):
            build_charts(self.root, self.root / "templates/electrical")
        with self.assertRaises(ValueError):
            build_charts(self.root, self.source, self.root / "docs/charts")


if __name__ == "__main__":
    unittest.main()
