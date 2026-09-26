"""Regressions from the first real Actions run and report-policy safeguards."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import TypedDict

from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.validate import check_report, hashes, svg_files
from tests.support import reference_root

ROOT: Path = reference_root()


class IgnoredCheck(TypedDict):
    key: str


class ErcSheet(TypedDict):
    violations: list[dict[str, str | bool]]


class ErcReport(TypedDict):
    schema: str
    kicad_version: str
    included_severities: list[str]
    ignored_checks: list[IgnoredCheck]
    sheets: list[ErcSheet]


class RegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root: Path = Path(self.temp.name)
        self.config = load_config(ROOT, ROOT / "examples/projects/controller/project.json")

    ####

    def erc_report(self) -> ErcReport:
        return {
            "schema": "https://schemas.kicad.org/erc.v1.json",
            "kicad_version": "10.0.0",
            "included_severities": ["error", "warning", "exclusion"],
            "ignored_checks": [
                {"key": key} for key in self.config.validation.expected_ignored_checks.erc
            ],
            "sheets": [{"violations": []}],
        }

    ####

    def check(self, data: ErcReport) -> int:
        path: Path = self.root / "report.json"
        payload = {
            "$schema": data["schema"],
            **{key: value for key, value in data.items() if key != "schema"},
        }
        path.write_text(json.dumps(payload))
        return check_report(path, "erc", self.config)

    ####

    def test_known_local_state_does_not_change_source_identity(self) -> None:
        shutil.copytree(ROOT / "examples/projects", self.root / "examples/projects")
        before = hashes(self.root, self.config.source_roots)
        (self.root / "examples/projects/controller/kicad/controller.kicad_prl").write_text(
            "local preferences"
        )
        (self.root / "examples/projects/controller/kicad/fp-info-cache").write_text("local cache")
        self.assertEqual(before, hashes(self.root, self.config.source_roots))

    ####

    def test_other_new_source_still_changes_inventory(self) -> None:
        shutil.copytree(ROOT / "examples/projects", self.root / "examples/projects")
        before = hashes(self.root, self.config.source_roots)
        (self.root / "examples/projects/controller/kicad/new.kicad_sch").write_text("unregistered")
        self.assertNotEqual(before, hashes(self.root, self.config.source_roots))

    ####

    def test_pcb_svg_is_a_file_not_a_directory(self) -> None:
        path: Path = self.root / "pcb.svg"
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.assertEqual(svg_files(self.root, "pcb_svg"), [path])

    ####

    def test_schematic_svg_uses_a_directory(self) -> None:
        (self.root / "schematic").mkdir()
        path: Path = self.root / "schematic/sheet.svg"
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.assertEqual(svg_files(self.root, "schematic_svg"), [path])

    ####

    def test_non_svg_xml_rejected(self) -> None:
        (self.root / "pcb.svg").write_text("<not_svg/>")
        with self.assertRaises(ValueError):
            svg_files(self.root, "pcb_svg")
        ####

    ####

    def test_pinned_report_policy_passes(self) -> None:
        self.assertEqual(self.check(self.erc_report()), 0)

    ####

    def test_new_disabled_check_rejected(self) -> None:
        data = self.erc_report()
        data["ignored_checks"].append({"key": "pin_not_connected"})
        with self.assertRaisesRegex(ValueError, "Disabled-check"):
            self.check(data)
        ####

    ####

    def test_missing_ignored_inventory_rejected(self) -> None:
        data = self.erc_report()
        del data["ignored_checks"]
        with self.assertRaisesRegex(TypeError, "ignored-check"):
            self.check(data)
        ####

    ####

    def test_suppressed_warning_output_rejected(self) -> None:
        data = self.erc_report()
        data["included_severities"] = ["error"]
        with self.assertRaisesRegex(ValueError, "warnings"):
            self.check(data)
        ####

    ####

    def test_stale_report_version_rejected(self) -> None:
        data = self.erc_report()
        data["kicad_version"] = "9.0.0"
        with self.assertRaisesRegex(ValueError, "identity"):
            self.check(data)


if __name__ == "__main__":
    unittest.main()
