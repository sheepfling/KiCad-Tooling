"""Reviewed model-population plans bind all inputs and recover partial write failures."""
from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo import model_population
from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.model_population import (
    ModelMap,
    ModelMapAssignment,
    ModelPopulationReport,
    populate_models,
)
from kicad_tooling.hwrepo.models import ProjectManifest
from tests.support import reference_root

PROJECT = "arduino-uno-status-led"
ISLAND = f"examples/projects/{PROJECT}"
BOARD = f"{ISLAND}/kicad/{PROJECT}.kicad_pcb"
MANIFEST = f"{ISLAND}/project.json"
MODEL = f"{ISLAND}/kicad/models/Header_1x02.step"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ModelPopulationSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="model-population-safety-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "repository"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git", "build"))
        self.board = self.root / BOARD
        self.manifest = self.root / MANIFEST
        self.model = self.root / MODEL
        self.model.parent.mkdir(parents=True)
        self.model.write_bytes(b"ISO-10303-21;\nEND-ISO-10303-21;\n")
        self.spec = ModelMap(project_id=PROJECT, board_sha256=digest(self.board.read_bytes()),
                             manifest_sha256=digest(self.manifest.read_bytes()),
                             assignments=(ModelMapAssignment(reference="J1", model=MODEL),))

    def plan(self) -> ModelPopulationReport:
        result = populate_models(self.root, PROJECT, self.spec)
        self.assertEqual(result.status, "PLAN", result.error)
        self.assertIsNotNone(result.locked_map)
        self.spec = read_model(Path(result.locked_map or ""), ModelMap)
        return result

    def test_reviewed_receipt_does_not_bypass_digest_locked_map(self) -> None:
        original_spec = self.spec
        original_board = self.board.read_bytes()
        original_manifest = self.manifest.read_bytes()
        plan = self.plan()
        result = populate_models(self.root, PROJECT, original_spec, apply=True, reviewed_plan=plan)
        self.assertEqual(result.status, "FAIL")
        self.assertIn("digest-locked map", result.error or "")
        self.assertEqual(self.board.read_bytes(), original_board)
        self.assertEqual(self.manifest.read_bytes(), original_manifest)

    def test_manifest_change_after_preview_rejects_apply_with_unchanged_board(self) -> None:
        plan = self.plan()
        original_board = self.board.read_bytes()
        changed_manifest = self.manifest.read_bytes() + b"\n"
        self.manifest.write_bytes(changed_manifest)
        result = populate_models(self.root, PROJECT, self.spec, apply=True, reviewed_plan=plan)
        self.assertEqual(result.status, "FAIL")
        self.assertIn("changed", result.error or "")
        self.assertEqual(self.board.read_bytes(), original_board)
        self.assertEqual(self.manifest.read_bytes(), changed_manifest)
        self.assertEqual(result.board_sha256, plan.board_sha256)
        self.assertNotEqual(result.manifest_sha256, plan.manifest_sha256)

    def test_model_change_after_preview_rejects_apply_with_unchanged_board(self) -> None:
        plan = self.plan()
        original_board = self.board.read_bytes()
        original_manifest = self.manifest.read_bytes()
        changed_model = self.model.read_bytes() + b"/* later vendor revision */\n"
        self.model.write_bytes(changed_model)
        result = populate_models(self.root, PROJECT, self.spec, apply=True, reviewed_plan=plan)
        self.assertEqual(result.status, "FAIL")
        self.assertIn("model source changed since review", result.error or "")
        self.assertEqual(self.board.read_bytes(), original_board)
        self.assertEqual(self.manifest.read_bytes(), original_manifest)
        self.assertEqual(self.model.read_bytes(), changed_model)
        self.assertEqual(result.board_sha256, plan.board_sha256)
        self.assertNotEqual(result.model_sha256, plan.model_sha256)

    def test_changed_reference_or_model_map_cannot_reuse_a_reviewed_plan(self) -> None:
        plan = self.plan()
        original_board = self.board.read_bytes()
        original_manifest = self.manifest.read_bytes()
        alternate = self.model.with_name("Alternate.step")
        alternate.write_bytes(self.model.read_bytes())
        for assignment in (
            ModelMapAssignment(reference="R1", model=MODEL, model_sha256=digest(self.model.read_bytes())),
            ModelMapAssignment(reference="J1", model=alternate.relative_to(self.root).as_posix(),
                               model_sha256=digest(alternate.read_bytes())),
        ):
            changed = self.spec.model_copy(update={"assignments": (assignment,)})
            with self.subTest(assignment=assignment):
                result = populate_models(self.root, PROJECT, changed, apply=True, reviewed_plan=plan)
                self.assertEqual(result.status, "FAIL")
                self.assertIn("changed since the reviewed plan", result.error or "")
                self.assertEqual(self.board.read_bytes(), original_board)
                self.assertEqual(self.manifest.read_bytes(), original_manifest)

    def test_linked_derived_pcb_is_rejected_before_reading_or_writing_it(self) -> None:
        plan = self.plan()
        outside = self.base / "outside.kicad_pcb"
        original_board = self.board.read_bytes()
        original_manifest = self.manifest.read_bytes()
        outside.write_bytes(original_board)
        self.board.unlink()
        try:
            self.board.symlink_to(outside)
        except OSError as exc:
            self.skipTest(str(exc))
        for apply in (False, True):
            with self.subTest(apply=apply):
                result = populate_models(self.root, PROJECT, self.spec, apply=apply,
                                         reviewed_plan=plan if apply else None)
                self.assertEqual(result.status, "FAIL")
                self.assertIn("Linked repository path", result.error or "")
                self.assertIsNone(result.board_sha256)
                self.assertTrue(self.board.is_symlink())
                self.assertEqual(outside.read_bytes(), original_board)
                self.assertEqual(self.manifest.read_bytes(), original_manifest)

    def test_manifest_write_failure_restores_only_the_tool_own_changes(self) -> None:
        original_replace = model_population._replace_bytes
        original_board = self.board.read_bytes()
        original_manifest = self.manifest.read_bytes()
        original_model = self.model.read_bytes()
        for fail_after_write in (False, True):
            plan = self.plan()
            failure_seen = False

            def fail_manifest_once(path: Path, value: bytes, after_write: bool = fail_after_write) -> None:
                nonlocal failure_seen
                if path == self.manifest and not failure_seen:
                    failure_seen = True
                    if after_write:
                        original_replace(path, value)
                    raise OSError("injected manifest publication failure")
                original_replace(path, value)

            with self.subTest(after_write=fail_after_write), patch(
                "kicad_tooling.hwrepo.model_population._replace_bytes", side_effect=fail_manifest_once,
            ):
                result = populate_models(self.root, PROJECT, self.spec, apply=True, reviewed_plan=plan)
            self.assertTrue(failure_seen)
            self.assertEqual(result.status, "FAIL")
            self.assertIn("injected manifest publication failure", result.error or "")
            self.assertEqual(self.board.read_bytes(), original_board)
            self.assertEqual(self.manifest.read_bytes(), original_manifest)
            self.assertEqual(self.model.read_bytes(), original_model)
            self.assertFalse(tuple(self.board.parent.glob(".*.model-map-*")))
            self.assertFalse(tuple(self.manifest.parent.glob(".*.model-map-*")))

    def test_rollback_does_not_clobber_a_separate_edit(self) -> None:
        plan = self.plan()
        original_manifest = self.manifest.read_bytes()
        original_replace = model_population._replace_bytes
        independent_board = self.board.read_bytes() + b"\n# independent change\n"

        def interfere_with_manifest(path: Path, value: bytes) -> None:
            if path == self.manifest:
                self.board.write_bytes(independent_board)
                raise OSError("external edit arrived before manifest publication")
            original_replace(path, value)

        with patch("kicad_tooling.hwrepo.model_population._replace_bytes", side_effect=interfere_with_manifest):
            result = populate_models(self.root, PROJECT, self.spec, apply=True, reviewed_plan=plan)
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(self.board.read_bytes(), independent_board)
        self.assertEqual(self.manifest.read_bytes(), original_manifest)

    def test_typed_preview_apply_changes_only_requested_assignment_and_inventory(self) -> None:
        def snapshot() -> dict[str, str]:
            return {path.relative_to(self.root).as_posix(): digest(path.read_bytes())
                    for path in self.root.rglob("*") if path.is_file()
                    and "build" not in path.relative_to(self.root).parts}

        original_sources = snapshot()
        original_board = self.board.read_bytes()
        original_manifest = read_model(self.manifest, ProjectManifest)
        plan = self.plan()
        saved_spec = read_model(Path(plan.run_directory) / "locked-model-map.json", ModelMap)
        saved_plan = read_model(Path(plan.run_directory) / "model-population.json", ModelPopulationReport)
        self.assertEqual(saved_spec, self.spec)
        self.assertEqual(saved_plan, plan)
        self.assertEqual(snapshot(), original_sources)
        result = populate_models(self.root, PROJECT, saved_spec, apply=True, reviewed_plan=saved_plan)
        self.assertEqual(result.status, "APPLIED", result.error)
        self.assertEqual(result.board_diff, plan.board_diff)
        self.assertEqual(result.manifest_diff, plan.manifest_diff)
        changed = snapshot()
        self.assertEqual({name for name in original_sources if original_sources[name] != changed[name]},
                         {BOARD, MANIFEST})
        after = self.board.read_bytes()
        untouched_marker = b'  (footprint "StatusLedTraining:R_Axial_10mm"'
        self.assertEqual(after[after.index(untouched_marker):],
                         original_board[original_board.index(untouched_marker):])
        prefix_marker = b'      (layers "*.Cu" "*.Mask") (net 3 "/GND"))'
        self.assertEqual(after.split(prefix_marker, 1)[0], original_board.split(prefix_marker, 1)[0])
        self.assertEqual(after.count(b'(model "${KIPRJMOD}/models/Header_1x02.step"'), 1)
        manifest = read_model(self.manifest, ProjectManifest)
        self.assertEqual(manifest.model_dump(exclude={"required_inputs"}),
                         original_manifest.model_dump(exclude={"required_inputs"}))
        self.assertEqual(set(manifest.required_inputs),
                         set(original_manifest.required_inputs) | {"kicad/models/Header_1x02.step"})
        self.assertIn("inspect", result.review_notice.lower())
        self.assertTrue(any("kicad_tooling.verify" in command for command in result.next_commands))


if __name__ == "__main__":
    unittest.main()
