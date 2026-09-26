"""Reviewed, explicit model assignment plans preserve board source and inventory."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.model_inventory import inspect_models
from kicad_tooling.hwrepo.model_population import (
    ModelMap,
    ModelPopulationReport,
    _replace_bytes,
    init_model_map,
    populate_models,
)
from kicad_tooling.hwrepo.models import ProjectManifest
from tests.support import reference_root

PROJECT = "arduino-uno-status-led"
ISLAND = f"examples/projects/{PROJECT}"
BOARD = f"{ISLAND}/kicad/{PROJECT}.kicad_pcb"
MANIFEST = f"{ISLAND}/project.json"
MODEL = f"{ISLAND}/kicad/models/Header_1x02.step"


class ModelPopulationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="model-population-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repo"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git"))
        self.board = self.root / BOARD
        self.manifest = self.root / MANIFEST
        self.model = self.root / MODEL
        self.model.parent.mkdir(parents=True)
        self.model.write_bytes(b"ISO-10303-21;\nEND-ISO-10303-21;\n")
        self.map = self.root / "build/model-map.json"
        self.map.parent.mkdir(exist_ok=True)
        self.write_map()

    def write_map(
        self, *, reference: str = "J1", model: str = MODEL, digest: str | None = None
    ) -> None:
        data = {
            "schema_version": "1",
            "project_id": PROJECT,
            "board_sha256": digest or hashlib.sha256(self.board.read_bytes()).hexdigest(),
            "manifest_sha256": hashlib.sha256(self.manifest.read_bytes()).hexdigest(),
            "assignments": [{"reference": reference, "model": model}],
        }
        self.map.write_text(json.dumps(data), encoding="utf-8")

    def locked_map(self) -> Path:
        plan = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(plan.status, "PLAN", plan.error)
        self.assertIsNotNone(plan.locked_map)
        return Path(plan.locked_map or "")

    def test_plan_then_apply_changes_only_board_and_manifest(self) -> None:
        original_board = self.board.read_bytes()
        original_manifest = self.manifest.read_bytes()
        plan = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(plan.status, "PLAN", plan.error)
        self.assertEqual(ModelPopulationReport.model_validate_json(plan.model_dump_json()), plan)
        self.assertIn("${KIPRJMOD}/models/Header_1x02.step", plan.board_diff)
        self.assertIn("kicad/models/Header_1x02.step", plan.manifest_diff)
        self.assertEqual(self.board.read_bytes(), original_board)
        self.assertEqual(self.manifest.read_bytes(), original_manifest)
        self.assertTrue((Path(plan.run_directory) / "board.diff").is_file())
        self.assertTrue((Path(plan.run_directory) / "manifest.diff").is_file())
        self.assertEqual(ModelMap.model_validate_json(self.map.read_text()).project_id, PROJECT)
        self.assertIsNotNone(plan.locked_map)
        locked = ModelMap.model_validate_json(Path(plan.locked_map or "").read_text())
        self.assertEqual(
            locked.assignments[0].model_sha256, hashlib.sha256(self.model.read_bytes()).hexdigest()
        )

        unlocked = populate_models(self.root, PROJECT, self.map, apply=True)
        self.assertEqual(unlocked.status, "FAIL")
        self.assertIn("digest-locked map", unlocked.error or "")

        applied = populate_models(self.root, PROJECT, Path(plan.locked_map or ""), apply=True)
        self.assertEqual(applied.status, "APPLIED", applied.error)
        self.assertEqual(applied.board_diff, plan.board_diff)
        self.assertEqual(applied.manifest_diff, plan.manifest_diff)
        changed_board = self.board.read_bytes()
        self.assertEqual(
            changed_board,
            original_board.replace(
                b'(layers "*.Cu" "*.Mask") (net 3 "/GND")))',
                b'(layers "*.Cu" "*.Mask") (net 3 "/GND"))\n'
                b'    (model "${KIPRJMOD}/models/Header_1x02.step" '
                b"(offset (xyz 0 0 0)) (scale (xyz 1 1 1)) "
                b"(rotate (xyz 0 0 0)))\n  )",
                1,
            ),
        )
        manifest = read_model(self.manifest, ProjectManifest)
        self.assertIn("kicad/models/Header_1x02.step", manifest.required_inputs)
        inventory = inspect_models(self.root, load_config(self.root, MANIFEST))
        self.assertEqual(inventory.footprints[0].status, "READY", inventory.findings)
        self.assertEqual(inventory.footprints[0].models[0].source_path, MODEL)

    def test_cli_creates_draft_with_current_hashes_and_no_selected_models(self) -> None:
        self.map.unlink()
        raw_manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        raw_manifest["required_inputs"].append("kicad/models/Header_1x02.step")
        self.manifest.write_text(json.dumps(raw_manifest, indent=2) + "\n", encoding="utf-8")
        original_board = self.board.read_bytes()
        result = subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.visualize",
                "--root",
                str(self.root),
                "--project",
                PROJECT,
                "--init-model-map",
                "build/model-map.json",
                "--format",
                "json",
            ),
            cwd=reference_root(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = ModelPopulationReport.model_validate_json(result.stdout)
        self.assertEqual(report.status, "DRAFT")
        raw = json.loads(self.map.read_text(encoding="utf-8"))
        self.assertEqual(raw["board_sha256"], hashlib.sha256(self.board.read_bytes()).hexdigest())
        self.assertEqual(
            raw["manifest_sha256"], hashlib.sha256(self.manifest.read_bytes()).hexdigest()
        )
        self.assertEqual({item["reference"] for item in raw["assignments"]}, {"J1", "R1", "D1"})
        self.assertTrue(all(item["model"] == "" for item in raw["assignments"]))
        self.assertTrue(all("model_sha256" not in item for item in raw["assignments"]))
        self.assertEqual(
            next(item for item in raw["assignments"] if item["reference"] == "J1")[
                "candidate_assets"
            ],
            [MODEL],
        )
        self.assertEqual(self.board.read_bytes(), original_board)
        preview = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(preview.status, "FAIL")
        self.assertIn("choose a reviewed model path", preview.error or "")

    def test_manifest_drift_and_internal_error_have_clear_receipts(self) -> None:
        self.manifest.write_bytes(self.manifest.read_bytes() + b"\n")
        drift = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(drift.status, "FAIL")
        self.assertIn("manifest changed", (drift.error or "").lower())
        self.write_map()
        with patch(
            "kicad_tooling.hwrepo.model_population._board_edits", side_effect=RuntimeError("bug")
        ):
            failed = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(failed.status, "ERROR")
        self.assertIn("RuntimeError: bug", (Path(failed.run_directory) / "error.txt").read_text())
        self.assertEqual(
            json.loads((Path(failed.run_directory) / "run.json").read_text())["status"], "ERROR"
        )

    def test_model_bytes_must_match_the_reviewed_plan(self) -> None:
        locked = self.locked_map()
        original_board = self.board.read_bytes()
        original_manifest = self.manifest.read_bytes()
        self.model.write_bytes(self.model.read_bytes() + b"changed after plan")
        rejected = populate_models(self.root, PROJECT, locked, apply=True)
        self.assertEqual(rejected.status, "FAIL")
        self.assertIn("model source changed since review", rejected.error or "")
        self.assertEqual(self.board.read_bytes(), original_board)
        self.assertEqual(self.manifest.read_bytes(), original_manifest)
        refreshed = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(refreshed.status, "PLAN", refreshed.error)
        self.assertNotEqual(refreshed.model_sha256, rejected.model_sha256)

    def test_shared_model_root_must_match_registered_library(self) -> None:
        private = self.root / "examples/projects/controller/kicad/borrowed.step"
        private.write_bytes(b"STEP")
        raw = json.loads(self.manifest.read_text(encoding="utf-8"))
        raw["shared_source_roots"] = ["examples/projects/controller/kicad"]
        self.manifest.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
        self.write_map(model=private.relative_to(self.root).as_posix())
        rejected = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(rejected.status, "FAIL")
        self.assertIn("registered library_ids", rejected.error or "")

    def test_draft_map_staging_preserves_destination_on_error_and_reserves_receipt_names(
        self,
    ) -> None:
        target = self.root / "build/new-map.json"
        with patch(
            "kicad_tooling.hwrepo.model_population.os.link", side_effect=OSError("commit failed")
        ):
            failed = init_model_map(self.root, PROJECT, target)
        self.assertEqual(failed.status, "FAIL")
        self.assertFalse(target.exists())
        self.assertEqual(list(target.parent.glob(".draft-model-map-*")), [])
        collided = init_model_map(
            self.root,
            PROJECT,
            Path("build/collision/model-population.json"),
            output=Path("build/collision"),
        )
        self.assertEqual(collided.status, "FAIL")
        self.assertIn("collides with receipt", collided.error or "")
        self.assertTrue((self.root / "build/collision/model-population.json").is_file())

    def test_duplicate_board_reference_and_manifest_write_failure_leave_source_safe(self) -> None:
        original = self.board.read_text(encoding="utf-8")
        self.board.write_text(
            original.replace(
                '(property "Reference" "R1"',
                '(property "Reference" "J1"',
                1,
            ),
            encoding="utf-8",
        )
        self.write_map()
        ambiguous = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(ambiguous.status, "FAIL")
        self.assertIn("Duplicate placed footprint", ambiguous.error or "")

        self.board.write_text(original, encoding="utf-8")
        self.write_map()
        original_board = self.board.read_bytes()
        original_manifest = self.manifest.read_bytes()

        def fail_manifest(path: Path, value: bytes) -> None:
            if path == self.manifest:
                raise OSError("manifest write failed")
            _replace_bytes(path, value)

        with patch(
            "kicad_tooling.hwrepo.model_population._replace_bytes", side_effect=fail_manifest
        ):
            failed = populate_models(self.root, PROJECT, self.locked_map(), apply=True)
        self.assertEqual(failed.status, "FAIL")
        self.assertIn("manifest write failed", failed.error or "")
        self.assertEqual(self.board.read_bytes(), original_board)
        self.assertEqual(self.manifest.read_bytes(), original_manifest)

    def test_stale_hash_and_existing_model_fail_without_writes(self) -> None:
        old_digest = hashlib.sha256(self.board.read_bytes()).hexdigest()
        self.board.write_bytes(self.board.read_bytes() + b"\n")
        initial = self.board.read_bytes()
        stale = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(stale.status, "FAIL")
        self.assertIn("Board changed", stale.error or "")
        self.assertEqual(self.board.read_bytes(), initial)
        self.write_map(digest=hashlib.sha256(self.board.read_bytes()).hexdigest())
        first = populate_models(self.root, PROJECT, self.locked_map(), apply=True)
        self.assertEqual(first.status, "APPLIED", first.error)
        self.write_map()
        repeated = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(repeated.status, "FAIL")
        self.assertIn("already has", repeated.error or "")
        self.assertNotEqual(old_digest, hashlib.sha256(self.board.read_bytes()).hexdigest())

    def test_rejects_ambiguous_or_unapproved_model_sources(self) -> None:
        self.write_map(reference="X404")
        missing_ref = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(missing_ref.status, "FAIL")
        self.assertIn("No unique placed footprint", missing_ref.error or "")
        self.write_map(model=f"{ISLAND}/kicad/models/missing.step")
        missing_file = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(missing_file.status, "FAIL")
        self.assertIn("missing", missing_file.error or "")
        idf = self.model.with_suffix(".idf")
        idf.write_bytes(b"IDF")
        self.write_map(model=idf.relative_to(self.root).as_posix())
        invalid = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(invalid.status, "FAIL")
        self.assertIn("STEP/STP", invalid.error or "")
        outside = self.root / "unregistered.step"
        outside.write_bytes(b"STEP")
        self.write_map(model="unregistered.step")
        unregistered = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(unregistered.status, "FAIL")
        self.assertIn("declared", unregistered.error or "")

    def test_shared_model_is_added_to_shared_inventory(self) -> None:
        shared = self.root / "examples/libraries/status-led/Header_1x02.step"
        shared.write_bytes(b"STEP")
        shared_name = shared.relative_to(self.root).as_posix()
        self.write_map(model=shared_name)
        original_board = self.board.read_bytes()
        original_manifest = self.manifest.read_bytes()
        consumer = self.root / "examples/projects/raspberry-pi-status-led/project.json"
        blocked = populate_models(self.root, PROJECT, self.map)
        self.assertEqual(blocked.status, "FAIL")
        self.assertIn("examples/projects/raspberry-pi-status-led/project.json", blocked.error or "")
        self.assertIn(f"add {shared_name} to shared_inputs", blocked.error or "")
        self.assertIsNone(blocked.locked_map)
        self.assertEqual(self.board.read_bytes(), original_board)
        self.assertEqual(self.manifest.read_bytes(), original_manifest)

        consumer_data = json.loads(consumer.read_text(encoding="utf-8"))
        consumer_data["shared_inputs"].append(shared_name)
        consumer.write_text(json.dumps(consumer_data, indent=2) + "\n", encoding="utf-8")
        consumer_before_apply = consumer.read_bytes()
        result = populate_models(self.root, PROJECT, self.locked_map(), apply=True)
        self.assertEqual(result.status, "APPLIED", result.error)
        manifest = read_model(self.manifest, ProjectManifest)
        self.assertIn(shared_name, manifest.shared_inputs)
        self.assertEqual(consumer.read_bytes(), consumer_before_apply)
        self.assertIn(
            "${KIPRJMOD}/../../../libraries/status-led/Header_1x02.step",
            self.board.read_text(encoding="utf-8"),
        )

    def test_shared_consumer_inventory_is_rechecked_at_apply(self) -> None:
        shared = self.root / "examples/libraries/status-led/Header_1x02.step"
        shared.write_bytes(b"STEP")
        shared_name = shared.relative_to(self.root).as_posix()
        consumer = self.root / "examples/projects/raspberry-pi-status-led/project.json"
        consumer_data = json.loads(consumer.read_text(encoding="utf-8"))
        consumer_data["shared_inputs"].append(shared_name)
        consumer.write_text(json.dumps(consumer_data, indent=2) + "\n", encoding="utf-8")
        self.write_map(model=shared_name)
        locked = self.locked_map()
        consumer_data["shared_inputs"].remove(shared_name)
        consumer.write_text(json.dumps(consumer_data, indent=2) + "\n", encoding="utf-8")
        original_board = self.board.read_bytes()
        original_manifest = self.manifest.read_bytes()
        rejected = populate_models(self.root, PROJECT, locked, apply=True)
        self.assertEqual(rejected.status, "FAIL")
        self.assertIn(
            "examples/projects/raspberry-pi-status-led/project.json", rejected.error or ""
        )
        self.assertIn(f"add {shared_name} to shared_inputs", rejected.error or "")
        self.assertEqual(self.board.read_bytes(), original_board)
        self.assertEqual(self.manifest.read_bytes(), original_manifest)


if __name__ == "__main__":
    unittest.main()
