"""Static 3D-model inventory behavior on small, isolated PCB sources."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.model_inventory import ModelInventoryReport, inspect_models
from tests.support import reference_root

ROOT = reference_root()


class ModelInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="model-inventory-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.project_dir = self.root / "projects/test-board/kicad"
        self.project_dir.mkdir(parents=True)
        self.board = self.project_dir / "test-board.kicad_pcb"
        base = load_config(ROOT, "examples/projects/controller/project.json")
        self.config = base.model_copy(update={
            "project_id": "test-board",
            "project": "projects/test-board/kicad/test-board.kicad_pro",
            "source_roots": ("projects/test-board/kicad",),
            "required_inputs": ("projects/test-board/kicad/test-board.kicad_pcb",),
        })

    def write_board(self, footprint: str) -> None:
        self.board.write_text("(kicad_pcb\n" + footprint + "\n)\n", encoding="utf-8")

    def test_unassigned_footprint_is_review_with_exact_stem_candidate(self) -> None:
        model = self.project_dir / "models/Part.step"
        model.parent.mkdir()
        model.write_text("candidate", encoding="utf-8")
        self.config = self.config.model_copy(update={
            "required_inputs": (*self.config.required_inputs,
                                "projects/test-board/kicad/models/Part.step"),
        })
        self.write_board('(footprint "Lib:Part" (property "Reference" "U1"))')
        report = inspect_models(self.root, self.config)
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(report.footprints[0].reference, "U1")
        self.assertEqual(report.footprints[0].candidate_assets,
                         ("projects/test-board/kicad/models/Part.step",))
        self.assertEqual(report.findings[0].code, "MODEL_UNASSIGNED")
        self.assertEqual(ModelInventoryReport.model_validate_json(report.model_dump_json()), report)

    def test_local_declared_model_is_ready_and_missing_or_unlisted_model_fails(self) -> None:
        model = self.project_dir / "models/Part.step"
        model.parent.mkdir()
        self.write_board('''(footprint "Lib:Part"
  (property "Reference" "U1")
  (model "${KIPRJMOD}/models/Part.step" (offset (xyz 0 0 0)))
)''')
        missing = inspect_models(self.root, self.config)
        self.assertEqual(missing.status, "FAIL")
        self.assertEqual(missing.footprints[0].models[0].resolution, "broken")
        model.write_text("source", encoding="utf-8")
        unlisted = inspect_models(self.root, self.config)
        self.assertEqual(unlisted.status, "FAIL")
        self.assertIn("required_inputs", unlisted.footprints[0].models[0].reason or "")
        self.config = self.config.model_copy(update={
            "required_inputs": (*self.config.required_inputs,
                                "projects/test-board/kicad/models/Part.step"),
        })
        ready = inspect_models(self.root, self.config)
        self.assertEqual(ready.status, "READY", ready.findings)
        self.assertEqual(ready.footprints[0].models[0].source_path,
                         "projects/test-board/kicad/models/Part.step")

    def test_unsupported_file_is_not_counted_as_a_model(self) -> None:
        model = self.project_dir / "models/Part.txt"
        model.parent.mkdir()
        model.write_text("not a 3D model", encoding="utf-8")
        self.config = self.config.model_copy(update={
            "required_inputs": (*self.config.required_inputs,
                                "projects/test-board/kicad/models/Part.txt"),
        })
        self.write_board('''(footprint "Lib:Part" (property "Reference" "U1")
  (model "${KIPRJMOD}/models/Part.txt"))''')
        result = inspect_models(self.root, self.config)
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.footprints[0].models[0].resolution, "broken")
        self.assertIn("Unsupported", result.footprints[0].models[0].reason or "")

    def test_shared_model_requires_declaration_and_stays_in_its_island(self) -> None:
        shared = self.root / "libraries/common/Part.step"
        shared.parent.mkdir(parents=True)
        shared.write_text("shared source", encoding="utf-8")
        self.write_board('''(footprint "Lib:Part" (property "Reference" "U1")
  (model "${KIPRJMOD}/../../../libraries/common/Part.step"))''')
        self.assertEqual(inspect_models(self.root, self.config).status, "FAIL")
        self.config = self.config.model_copy(update={
            "source_roots": (*self.config.source_roots, "libraries/common"),
            "required_inputs": (*self.config.required_inputs, "libraries/common/Part.step"),
        })
        result = inspect_models(self.root, self.config)
        self.assertEqual(result.status, "READY", result.findings)
        self.assertEqual(result.footprints[0].models[0].source_path, "libraries/common/Part.step")

    def test_standard_library_is_review_until_checked_in_pinned_kicad(self) -> None:
        self.write_board('''(footprint "Lib:Part" (property "Reference" "U1")
  (model "${KICAD10_3DMODEL_DIR}/Package.3dshapes/Part.wrl"))''')
        report = inspect_models(self.root, self.config)
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(report.footprints[0].models[0].resolution, "toolchain_dependent")
        self.assertEqual(report.findings[0].code, "MODEL_TOOLCHAIN")

    def test_vrml_only_model_warns_that_step_body_may_be_absent(self) -> None:
        model = self.project_dir / "models/Part.wrl"
        model.parent.mkdir()
        model.write_text("VRML source", encoding="utf-8")
        self.config = self.config.model_copy(update={
            "required_inputs": (*self.config.required_inputs,
                                "projects/test-board/kicad/models/Part.wrl"),
        })
        self.write_board('''(footprint "Lib:Part" (property "Reference" "U1")
  (model "${KIPRJMOD}/models/Part.wrl"))''')
        report = inspect_models(self.root, self.config)
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(report.footprints[0].status, "REVIEW")
        self.assertEqual(report.findings[0].code, "MODEL_STEP_SUBSTITUTE")
        partner = model.with_suffix(".step")
        partner.write_text("STEP source", encoding="utf-8")
        self.config = self.config.model_copy(update={
            "required_inputs": (*self.config.required_inputs,
                                "projects/test-board/kicad/models/Part.step"),
        })
        ready = inspect_models(self.root, self.config)
        self.assertEqual(ready.status, "READY", ready.findings)

    def test_idf_model_needs_a_viewable_body(self) -> None:
        model = self.project_dir / "models/Part.idf"
        model.parent.mkdir()
        model.write_text("IDF source", encoding="utf-8")
        self.config = self.config.model_copy(update={
            "required_inputs": (*self.config.required_inputs,
                                "projects/test-board/kicad/models/Part.idf"),
        })
        self.write_board('''(footprint "Lib:Part" (property "Reference" "U1")
  (model "${KIPRJMOD}/models/Part.idf"))''')
        report = inspect_models(self.root, self.config)
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(report.footprints[0].status, "REVIEW")
        self.assertEqual(report.findings[0].code, "MODEL_IDF_ONLY")
        step = model.with_suffix(".step")
        step.write_text("STEP source", encoding="utf-8")
        self.config = self.config.model_copy(update={
            "required_inputs": (*self.config.required_inputs,
                                "projects/test-board/kicad/models/Part.step"),
        })
        self.write_board('''(footprint "Lib:Part" (property "Reference" "U1")
  (model "${KIPRJMOD}/models/Part.idf")
  (model "${KIPRJMOD}/models/Part.step"))''')
        mixed = inspect_models(self.root, self.config)
        self.assertEqual(mixed.status, "READY", mixed.findings)

    def test_embedded_model_record_must_exist(self) -> None:
        self.write_board('''(footprint "Lib:Part" (property "Reference" "U1")
  (model "kicad-embed://Part.step"))''')
        self.assertEqual(inspect_models(self.root, self.config).status, "FAIL")
        self.write_board('''(footprint "Lib:Part" (property "Reference" "U1")
  (model "kicad-embed://Part.step"))
  (embedded_files (file (name "Part.step") (type model)
    (data |YWJj|) (checksum "AABB")))''')
        report = inspect_models(self.root, self.config)
        self.assertEqual(report.status, "READY", report.findings)
        self.assertEqual(report.footprints[0].models[0].resolution, "embedded_present")

    def test_balanced_parser_ignores_quoted_parens_and_comment_footprints(self) -> None:
        model = self.project_dir / "models/Part(1).step"
        model.parent.mkdir()
        model.write_text("source", encoding="utf-8")
        self.config = self.config.model_copy(update={
            "required_inputs": (*self.config.required_inputs,
                                "projects/test-board/kicad/models/Part(1).step"),
        })
        self.write_board('''# (footprint "Comment:Fake")
  (footprint "Lib:Part"
    (property "Reference" "U1")
    (property "Value" "quoted ) (footprint \\\"Fake\\\")")
    (model "${KIPRJMOD}/models/Part(1).step" (offset (xyz 0 0 0)))
  )''')
        report = inspect_models(self.root, self.config)
        self.assertEqual(report.status, "READY", report.findings)
        self.assertEqual(len(report.footprints), 1)
        self.assertEqual(len(report.footprints[0].models), 1)

    def test_hidden_only_model_and_malformed_board_are_explained(self) -> None:
        model = self.project_dir / "Part.step"
        model.write_text("source", encoding="utf-8")
        self.config = self.config.model_copy(update={
            "required_inputs": (*self.config.required_inputs, "projects/test-board/kicad/Part.step"),
        })
        self.write_board('''(footprint "Lib:Part" (property "Reference" "U1")
  (model "${KIPRJMOD}/Part.step" (hide yes)))''')
        report = inspect_models(self.root, self.config)
        self.assertEqual(report.status, "REVIEW")
        self.assertTrue(report.footprints[0].models[0].hidden)
        self.assertEqual(report.findings[0].code, "MODEL_HIDDEN")
        self.board.write_text('(kicad_pcb (footprint "Lib:Part"', encoding="utf-8")
        malformed = inspect_models(self.root, self.config)
        self.assertEqual(malformed.status, "FAIL")
        self.assertEqual(malformed.findings[0].code, "MODEL_BOARD_PARSE")


if __name__ == "__main__":
    unittest.main()
