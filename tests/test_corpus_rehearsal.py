"""Source identity and installed-package boundaries for the corpus rehearsal."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import rehearse_corpus as rehearsal


class CorpusRehearsalTests(unittest.TestCase):
    def test_recorded_run_still_reports_unexercised_engineering_stages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rehearsal.write_report(
                root,
                {
                    "status": "RECORDED",
                    "selected": 1,
                    "completed": 1,
                    "results": [
                        {
                            "fixture": {"id": "board", "repository": "example/board"},
                            "stages": [{"stage": "native", "status": "PASS"}],
                        }
                    ],
                },
            )
            report = (root / "REPORT.md").read_text()
            self.assertIn("NOT_RUN", report)
            self.assertIn("transient_and_frequency_simulations", report)
            self.assertIn("release_revision_package_and_restore", report)

    def test_inventory_rejects_changed_and_extra_source_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources/board"
            source.mkdir(parents=True)
            board = source / "board.kicad_pro"
            board.write_text("original")
            inventory = {
                "inventory_complete": True,
                "files": [
                    {"path": board.name, "kind": "file", "sha256": rehearsal.digest(board)},
                ],
            }
            rehearsal.save(root / "inventory.json", inventory)
            group = {
                "inventory_path": "inventory.json",
                "directory": "sources/board",
                "source_kind": "git_snapshot",
                "inventory_sha256": rehearsal.signature(inventory),
            }
            self.assertEqual(rehearsal.verify_group(root, group), [])
            board.write_text("changed")
            (source / "extra.txt").write_text("extra")
            problems = rehearsal.verify_group(root, group)
            self.assertIn("Missing/changed: board.kicad_pro", problems)
            self.assertIn("Uninventoried: extra.txt", problems)
            self.assertEqual(board.read_text(), "changed")

    def test_inventory_observes_symlinks_without_following_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "snapshot").mkdir()
            (root / "snapshot/link").symlink_to("../../outside")
            inventory = {
                "inventory_complete": True,
                "files": [
                    {"path": "link", "kind": "symlink", "target": "../../outside"},
                ],
            }
            rehearsal.save(root / "inventory.json", inventory)
            group = {
                "inventory_path": "inventory.json",
                "directory": "snapshot",
                "source_kind": "git_snapshot",
                "inventory_sha256": rehearsal.signature(inventory),
            }
            self.assertEqual(rehearsal.verify_group(root, group), [])
            with self.assertRaisesRegex(ValueError, "Linked source"):
                rehearsal.inside(root, "snapshot/link/file.kicad_pro")
            with self.assertRaises(ValueError):
                rehearsal.inside(root, "../outside")

    def test_command_uses_isolated_installed_module_and_external_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            completed = subprocess.CompletedProcess([], 1, '{"status":"FAIL"}', "")
            with patch.object(rehearsal.subprocess, "run", return_value=completed) as execute:
                report = rehearsal.run(
                    root, "verify", root / "project", "verify", "--project", "example"
                )
            argv = execute.call_args.args[0]
            self.assertEqual(argv[1:5], ["-I", "-B", "-m", "kicad_tooling"])
            self.assertNotIn("PYTHONPATH", execute.call_args.kwargs["env"])
            self.assertEqual(report["returncode"], 1)
            self.assertIsNone(report["parse_error"])
            self.assertEqual(json.loads((root / "verify.json").read_text())["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
