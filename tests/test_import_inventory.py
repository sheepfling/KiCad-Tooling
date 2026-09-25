"""Bulk intake is a read-only collection of ordinary one-project previews."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from kicad_tooling.hwrepo.import_inventory import scan_imports
from kicad_tooling.hwrepo.models import ImportInventoryReport, ProjectKind
from kicad_tooling.template import main as template_main
from tests.support import reference_root


class ImportInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="kicad-scan-imports-")
        self.addCleanup(temporary.cleanup)
        self.source = Path(temporary.name) / "Old boards"
        self.source.mkdir()

    def write_candidate(self, relative: str, schematic: bool = True,
                        pcb: bool = False) -> Path:
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        if schematic:
            path.with_suffix(".kicad_sch").write_text("(kicad_sch)", encoding="utf-8")
        if pcb:
            path.with_suffix(".kicad_pcb").write_text("(kicad_pcb)", encoding="utf-8")
        return path

    def test_nested_and_sibling_projects_receive_individual_dry_run_previews(self) -> None:
        first = self.write_candidate("Power board.kicad_pro", pcb=True)
        second = self.write_candidate("sub/LED board.kicad_pro", schematic=False, pcb=True)
        ignored = self.write_candidate("build/old.kicad_pro", pcb=True)
        before = {path: path.read_bytes() for path in (first, second, ignored)}

        report = scan_imports(reference_root(), self.source, "kicad-10.0.5")

        self.assertEqual(report.status, "PASS", report.issues)
        self.assertFalse(report.copied)
        self.assertEqual(tuple(item.suggested_project_id for item in report.candidates),
                         ("power-board", "sub-led-board"))
        self.assertEqual(tuple(item.kind for item in report.candidates),
                         (ProjectKind.PCB, ProjectKind.PCB_ONLY))
        self.assertTrue(all(item.preview.dry_run and item.preview.status == "PASS"
                            for item in report.candidates))
        self.assertIn("--source '", report.candidates[0].next_command)
        self.assertIn("kicad_tooling.template diagnose", report.candidates[0].next_command)
        self.assertIn("build/old.kicad_pro", report.skipped_local_state)
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertFalse((reference_root() / "projects/power-board").exists())

    def test_bad_candidate_does_not_hide_good_candidate(self) -> None:
        self.write_candidate("good.kicad_pro", pcb=True)
        self.write_candidate("no-design.kicad_pro", schematic=False)
        report = scan_imports(reference_root(), self.source, "kicad-10.0.5")
        self.assertEqual(report.status, "NEEDS_WORK")
        self.assertEqual(len(report.candidates), 2)
        self.assertEqual(report.candidates[0].preview.status, "PASS")
        self.assertEqual(report.candidates[1].preview.status, "FAIL")
        self.assertIn("matching .kicad_sch or .kicad_pcb",
                      report.candidates[1].preview.issues[0])

    def test_cli_text_is_brief_and_json_retains_exclusion_detail(self) -> None:
        self.write_candidate("battery.kicad_pro", pcb=True)
        argv = ["kicad_tooling.template", "scan-imports", "--root", str(reference_root()),
                "--source-dir", str(self.source), "--toolchain", "kicad-10.0.5"]
        with (patch.object(sys, "argv", argv),
              patch("sys.stdout", new_callable=StringIO) as output):
            self.assertEqual(template_main(), 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["lane"], "IMPORT_INVENTORY")
        self.assertFalse(payload["copied"])
        self.assertIn("copied_sha256", payload["candidates"][0]["preview"])
        with (patch.object(sys, "argv", [*argv, "--format", "text"]),
              patch("sys.stdout", new_callable=StringIO) as output):
            self.assertEqual(template_main(), 0)
        self.assertIn("Import inventory: PASS; 1 candidate", output.getvalue())
        self.assertIn("suggested ID: battery", output.getvalue())

    def test_inventory_json_contract_round_trips_and_rejects_invalid_boundaries(self) -> None:
        self.write_candidate("battery.kicad_pro", pcb=True)
        report = scan_imports(reference_root(), self.source, "kicad-10.0.5")
        payload = json.loads(report.model_dump_json())
        self.assertEqual(ImportInventoryReport.model_validate_json(
            json.dumps(payload)), report)
        cases = (
            {**payload, "schema_version": "2"},
            {**payload, "copied": "false"},
            {**payload, "copied": True},
            {**payload, "invented_field": True},
            {**payload, "candidates": [{**payload["candidates"][0], "invented_field": True}]},
        )
        for invalid in cases:
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                ImportInventoryReport.model_validate_json(json.dumps(invalid))


if __name__ == "__main__":
    unittest.main()
