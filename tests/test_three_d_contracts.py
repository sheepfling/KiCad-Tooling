"""Strict 3D wire reports retain malformed-source findings without granting approval."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.model_inventory import inspect_models
from kicad_tooling.hwrepo.models import (
    FootprintModels,
    ModelAssignment,
    ModelInventoryReport,
    ModelMap,
    ModelMapAssignment,
    ModelPopulationReport,
    ThreeDReport,
)
from kicad_tooling.hwrepo.three_d import generate
from tests.support import reference_root

PROJECT = "arduino-uno-status-led"
ISLAND = f"examples/projects/{PROJECT}"
BOARD = f"{ISLAND}/kicad/{PROJECT}.kicad_pcb"


class ThreeDContractTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="three-d-contract-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repository"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git", "build"))
        self.board = self.root / BOARD
        self.config = load_config(self.root, f"{ISLAND}/project.json")
        self.inventory = inspect_models(self.root, self.config)
        self.report = ThreeDReport(
            project_id=PROJECT,
            mode="inspect",
            status="PASS",
            run_directory=str(self.root / "build/diagnostics/contract-fixture"),
            toolchain_id=self.config.toolchain_id,
            kicad_version=self.config.kicad_version,
            board=BOARD,
            source_sha256={BOARD: hashlib.sha256(self.board.read_bytes()).hexdigest()},
            models=self.inventory,
        )

    def test_real_inspection_receipts_round_trip_through_canonical_contracts(self) -> None:
        with patch("kicad_tooling.hwrepo.three_d.doctor") as native:
            report = generate(self.root, PROJECT, check_models=True)
        native.assert_not_called()
        self.assertEqual(report.status, "PASS")
        self.assertFalse(report.build_authorized)
        self.assertIsInstance(report.models, ModelInventoryReport)
        self.assertEqual(ThreeDReport.model_validate_json(report.model_dump_json()), report)
        receipt = Path(report.run_directory)
        self.assertEqual(
            ThreeDReport.model_validate_json((receipt / "visualization.json").read_text()),
            report,
        )
        self.assertEqual(
            ModelInventoryReport.model_validate_json((receipt / "models.json").read_text()),
            report.models,
        )
        self.assertFalse(report.models.build_authorized)
        self.assertFalse(report.commands)
        self.assertFalse(report.artifacts_sha256)

    def test_reports_publish_closed_schemas_with_no_build_authority(self) -> None:
        for contract in (ModelInventoryReport, ThreeDReport):
            with self.subTest(contract=contract.__name__):
                schema = contract.model_json_schema()
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual(schema["properties"]["schema_version"]["const"], "1")
                self.assertIs(schema["properties"]["build_authorized"]["const"], False)

    def test_reports_reject_unsupported_version_unknown_fields_and_scalar_coercion(self) -> None:
        for report in (self.inventory, self.report):
            data = report.model_dump(mode="json")
            for update in (
                {"schema_version": "2"},
                {"schema_version": 1},
                {"unrecognized": "field"},
                {"project_id": 17},
                {"build_authorized": True},
                {"build_authorized": "false"},
                {"status": "APPROVED"},
            ):
                with (
                    self.subTest(contract=type(report).__name__, update=update),
                    self.assertRaises(ValidationError),
                ):
                    type(report).model_validate_json(json.dumps(data | update))

    def test_reports_reject_empty_paths_invalid_identifiers_and_bad_digests(self) -> None:
        inventory = self.inventory.model_dump(mode="json")
        for update in ({"project_id": "../other"}, {"board": ""}, {"next_actions": [""]}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ModelInventoryReport.model_validate_json(json.dumps(inventory | update))
        report = self.report.model_dump(mode="json")
        for update in (
            {"run_directory": ""},
            {"toolchain_id": "../other"},
            {"board": ""},
            {"source_sha256": {BOARD: "not-a-hash"}},
            {"artifacts_sha256": {"board.step": "A" * 64}},
            {"source_sha256": {"": "a" * 64}},
            {"runner": "shell"},
            {"mode": "approve"},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ThreeDReport.model_validate_json(json.dumps(report | update))

    def test_nested_assignment_contracts_validate_line_numbers_and_resolved_paths(self) -> None:
        assignment = ModelAssignment(
            path="${KIPRJMOD}/models/Part.step",
            line=3,
            resolution="source_present",
            source_path=f"{ISLAND}/kicad/models/Part.step",
        )
        self.assertEqual(
            ModelAssignment.model_validate_json(assignment.model_dump_json()), assignment
        )
        footprint = FootprintModels(
            reference="U1",
            footprint_id="Library:Part",
            line=2,
            models=(assignment,),
            candidate_assets=(assignment.source_path,),
            status="READY",
        )
        self.assertEqual(
            FootprintModels.model_validate_json(footprint.model_dump_json()), footprint
        )
        data = assignment.model_dump(mode="json")
        for update in (
            {"line": 0},
            {"line": True},
            {"line": "3"},
            {"hidden": "false"},
            {"source_path": ""},
            {"resolution": "approved"},
            {"extra": "field"},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ModelAssignment.model_validate_json(json.dumps(data | update))
        for update in ({"line": -1}, {"candidate_assets": [""]}, {"models": [data | {"line": 0}]}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                FootprintModels.model_validate_json(
                    json.dumps(footprint.model_dump(mode="json") | update)
                )

    def test_raw_broken_model_paths_and_unknown_references_remain_diagnosable(self) -> None:
        self.board.write_text(
            '(kicad_pcb\n  (footprint ""\n    (model "")\n  )\n)\n', encoding="utf-8"
        )
        report = inspect_models(self.root, self.config)
        self.assertEqual(report.status, "FAIL")
        footprint = report.footprints[0]
        self.assertEqual(footprint.reference, "<unknown@2>")
        self.assertEqual(footprint.footprint_id, "")
        self.assertEqual(footprint.models[0].path, "")
        self.assertEqual(footprint.models[0].line, 3)
        self.assertEqual(footprint.models[0].resolution, "broken")
        self.assertIn("Empty 3D model path", footprint.models[0].reason)
        self.assertIn(f"{BOARD}:3", {finding.location for finding in report.findings})
        self.assertEqual(ModelInventoryReport.model_validate_json(report.model_dump_json()), report)

    def test_model_map_round_trip_rejects_ambiguous_and_malformed_assignments(self) -> None:
        assignment = ModelMapAssignment(reference="J1", model=f"{ISLAND}/kicad/models/Part.step")
        model_map = ModelMap(
            project_id=PROJECT,
            board_sha256=hashlib.sha256(self.board.read_bytes()).hexdigest(),
            manifest_sha256=hashlib.sha256(
                (self.root / ISLAND / "project.json").read_bytes()
            ).hexdigest(),
            assignments=(assignment,),
        )
        self.assertEqual(ModelMap.model_validate_json(model_map.model_dump_json()), model_map)
        data = model_map.model_dump(mode="json")
        for update in (
            {"schema_version": "2"},
            {"schema_version": 1},
            {"extra": "field"},
            {"project_id": "../other"},
            {"board_sha256": "not-a-digest"},
            {"manifest_sha256": "not-a-digest"},
            {"assignments": []},
            {"assignments": [assignment.model_dump(), assignment.model_dump()]},
            {"assignments": [{"reference": "", "model": assignment.model}]},
            {"assignments": [{"reference": 1, "model": assignment.model}]},
            {"assignments": [assignment.model_dump() | {"extra": "field"}]},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ModelMap.model_validate_json(json.dumps(data | update))
        draft = ModelMap.model_validate_json(
            json.dumps(
                data
                | {
                    "assignments": [{"reference": "J1", "model": "", "candidate_assets": []}],
                }
            )
        )
        self.assertEqual(draft.assignments[0].model, "")
        missing_manifest = dict(data)
        del missing_manifest["manifest_sha256"]
        with self.assertRaises(ValidationError):
            ModelMap.model_validate_json(json.dumps(missing_manifest))

    def test_population_report_never_authorizes_build_or_skips_required_checks(self) -> None:
        digest = hashlib.sha256(self.board.read_bytes()).hexdigest()
        report = ModelPopulationReport(
            status="APPLIED",
            project_id=PROJECT,
            run_directory=str(self.root / "build/diagnostics/model-map"),
            board=BOARD,
            manifest=f"{ISLAND}/project.json",
            board_sha256=digest,
            model_sha256={f"{ISLAND}/kicad/models/Part.step": "a" * 64},
            next_commands=(
                f"python -B -m kicad_tooling.verify --project {PROJECT} --depth native",
            ),
        )
        self.assertEqual(
            ModelPopulationReport.model_validate_json(report.model_dump_json()), report
        )
        self.assertFalse(report.build_authorized)
        self.assertTrue(report.checks_required)
        schema = ModelPopulationReport.model_json_schema()
        self.assertIs(schema["properties"]["build_authorized"]["const"], False)
        self.assertIs(schema["properties"]["checks_required"]["const"], True)
        for update in (
            {"schema_version": "2"},
            {"unrecognized": "field"},
            {"project_id": 10},
            {"board_sha256": "bad"},
            {"model_sha256": {"model.step": "bad"}},
            {"board": ""},
            {"run_directory": ""},
            {"build_authorized": True},
            {"checks_required": False},
            {"status": "APPROVED"},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ModelPopulationReport.model_validate_json(
                    json.dumps(report.model_dump(mode="json") | update)
                )

    def test_linked_derived_board_is_rejected_before_inspection_or_native_execution(self) -> None:
        outside = self.root.parent / "outside.kicad_pcb"
        outside.write_text("private source outside the checkout", encoding="utf-8")
        self.board.unlink()
        try:
            self.board.symlink_to(outside)
        except OSError:
            self.skipTest("Symlink creation unavailable")
        with (
            patch("kicad_tooling.hwrepo.model_inventory._children") as parse,
            self.assertRaisesRegex(ValueError, "Linked repository path"),
        ):
            inspect_models(self.root, self.config)
        parse.assert_not_called()
        # Use the already resolved config to exercise the derived-board boundary,
        # independent of earlier manifest/input discovery checks.
        with (
            patch("kicad_tooling.hwrepo.three_d.load_config", return_value=self.config),
            patch("kicad_tooling.hwrepo.three_d.inspect_models") as inspect,
            patch("kicad_tooling.hwrepo.three_d._run_kicad") as run_native,
        ):
            report = generate(self.root, PROJECT, output=Path("build/linked-board"))
        self.assertEqual(report.status, "FAIL")
        self.assertIn("Linked repository path", report.error)
        self.assertFalse(report.build_authorized)
        self.assertFalse(report.artifacts_sha256)
        inspect.assert_not_called()
        run_native.assert_not_called()
        self.assertEqual(outside.read_text(), "private source outside the checkout")


if __name__ == "__main__":
    unittest.main()
