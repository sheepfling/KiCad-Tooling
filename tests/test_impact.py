"""Changed-path planning must be deterministic and fail closed on ambiguous scope."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.discovery import load_registry
from kicad_tooling.hwrepo.impact import plan_paths
from kicad_tooling.hwrepo.models import (
    Evidence,
    EvidenceKind,
    LibrariesCatalog,
    ProductRecord,
    ProjectManifest,
)
from tests.support import reference_root

ROOT: Path = reference_root()
ALL_IDS = (
    "arduino-uno-status-led",
    "controller",
    "passive-signal-reference",
    "raspberry-pi-status-led",
    "status-indicator-harness-interface",
    "status-indicator-wiring",
)
PRODUCT_IDS = (
    "arduino-uno-status-led",
    "raspberry-pi-status-led",
    "status-indicator-harness-interface",
    "status-indicator-wiring",
)


class ImpactPlanTests(unittest.TestCase):
    def test_changed_project_and_deleted_file_under_known_island_are_focused(self) -> None:
        plan = plan_paths(
            ROOT,
            (
                "examples/projects/controller/kicad/controller.kicad_pcb",
                "examples/projects/controller/kicad/removed.kicad_sch",
            ),
        )
        self.assertEqual(plan.scope, "focused")
        self.assertEqual(plan.projects, ("controller",))
        self.assertFalse(plan.docs_changed)
        self.assertEqual(plan.schema_version, "1")

    def test_indexed_product_path_selects_every_member(self) -> None:
        plan = plan_paths(ROOT, ("examples/products/status-indicator-system/product.json",))
        self.assertEqual(plan.scope, "focused")
        self.assertEqual(plan.projects, PRODUCT_IDS)

    def test_shared_library_asset_fans_out_to_declared_consumers(self) -> None:
        plan = plan_paths(ROOT, ("examples/libraries/status-led/status-led.kicad_sym",))
        self.assertEqual(plan.scope, "focused")
        self.assertEqual(
            plan.projects,
            (
                "arduino-uno-status-led",
                "raspberry-pi-status-led",
            ),
        )
        self.assertTrue(any("Shared dependency" in reason for reason in plan.reasons))

    def test_shared_library_markdown_is_policy_input_not_docs_only(self) -> None:
        plan = plan_paths(ROOT, ("examples/libraries/status-led/PROVENANCE.md",))
        self.assertEqual(plan.scope, "focused")
        self.assertEqual(
            plan.projects,
            (
                "arduino-uno-status-led",
                "raspberry-pi-status-led",
            ),
        )
        self.assertTrue(plan.docs_changed)

    def test_ordinary_markdown_only_uses_docs_scope(self) -> None:
        plan = plan_paths(
            ROOT,
            (
                "README.md",
                "examples/projects/controller/docs/design.md",
                "examples/products/status-indicator-system/README.md",
                "generated/README.md",
            ),
        )
        self.assertEqual(plan.scope, "docs")
        self.assertEqual(plan.projects, ())
        self.assertTrue(plan.docs_changed)

    def test_mixed_docs_and_source_keeps_only_source_project(self) -> None:
        plan = plan_paths(
            ROOT,
            (
                "examples/projects/controller/docs/design.md",
                "examples/projects/arduino-uno-status-led/kicad/arduino-uno-status-led.kicad_sch",
            ),
        )
        self.assertEqual(plan.scope, "focused")
        self.assertEqual(plan.projects, ("arduino-uno-status-led",))
        self.assertTrue(plan.docs_changed)

    def test_project_local_declared_markdown_input_is_source(self) -> None:
        project_manifest = ROOT / "examples/projects/controller/project.json"

        def synthetic_manifest(path: Path, model: type[BaseModel]) -> BaseModel:
            result = read_model(path, model)
            if path == project_manifest and isinstance(result, ProjectManifest):
                return result.model_copy(
                    update={
                        "required_inputs": (*result.required_inputs, "docs/declared.md"),
                        "source_roots": (*result.source_roots, "docs/source-notes"),
                    }
                )
            return result

        with patch("kicad_tooling.hwrepo.impact.read_model", side_effect=synthetic_manifest):
            for path in (
                "examples/projects/controller/docs/declared.md",
                "examples/projects/controller/docs/source-notes/entry.md",
            ):
                with self.subTest(path=path):
                    plan = plan_paths(ROOT, (path,))
                    self.assertEqual(plan.scope, "focused")
                    self.assertEqual(plan.projects, ("controller",))
                    self.assertTrue(plan.docs_changed)

    def test_product_mechanical_drawing_is_a_product_input(self) -> None:
        plan = plan_paths(ROOT, ("examples/products/status-indicator-system/docs/mechanical.md",))
        self.assertEqual(plan.scope, "focused")
        self.assertEqual(plan.projects, PRODUCT_IDS)

    def test_product_evidence_markdown_is_a_product_input(self) -> None:
        product_path = ROOT / "examples/products/status-indicator-system/product.json"

        def synthetic_product(path: Path, model: type[BaseModel]) -> BaseModel:
            result = read_model(path, model)
            if path == product_path and isinstance(result, ProductRecord):
                evidence = Evidence(
                    id="review-note",
                    kind=EvidenceKind.OBSERVATION,
                    path="docs/product-review.md",
                    sha256="0" * 64,
                    claims=(),
                )
                return result.model_copy(update={"evidence": (*result.evidence, evidence)})
            return result

        with patch("kicad_tooling.hwrepo.impact.read_model", side_effect=synthetic_product):
            plan = plan_paths(ROOT, ("docs/product-review.md",))
        self.assertEqual(plan.scope, "focused")
        self.assertEqual(plan.projects, PRODUCT_IDS)

    def test_library_license_markdown_outside_library_tree_selects_consumers(self) -> None:
        def synthetic_catalog(path: Path, model: type[BaseModel]) -> BaseModel:
            result = read_model(path, model)
            if isinstance(result, LibrariesCatalog):
                library = result.libraries[0].model_copy(
                    update={
                        "licensing_path": "docs/library-license.md",
                    }
                )
                return result.model_copy(update={"libraries": (library,)})
            return result

        with patch("kicad_tooling.hwrepo.impact.read_model", side_effect=synthetic_catalog):
            plan = plan_paths(ROOT, ("docs/library-license.md",))
        self.assertEqual(plan.scope, "focused")
        self.assertEqual(
            plan.projects,
            (
                "arduino-uno-status-led",
                "raspberry-pi-status-led",
            ),
        )

    def test_project_referenced_handoff_markdown_is_a_project_input(self) -> None:
        project_manifest = ROOT / "examples/projects/controller/project.json"

        def synthetic_manifest(path: Path, model: type[BaseModel]) -> BaseModel:
            result = read_model(path, model)
            if path == project_manifest and isinstance(result, ProjectManifest):
                return result.model_copy(
                    update={
                        "mechanical_handoff": "docs/mechanical-handoff.md",
                        "governance_record": "docs/governance.md",
                    }
                )
            return result

        with patch("kicad_tooling.hwrepo.impact.read_model", side_effect=synthetic_manifest):
            for path in (
                "examples/projects/controller/docs/mechanical-handoff.md",
                "examples/projects/controller/docs/governance.md",
            ):
                with self.subTest(path=path):
                    plan = plan_paths(ROOT, (path,))
                    self.assertEqual(plan.scope, "focused")
                    self.assertEqual(plan.projects, ("controller",))

    def test_global_and_policy_changes_fall_back_to_full(self) -> None:
        for path in (
            "tools/hwrepo/selection.py",
            "tests/test_governance.py",
            "catalog/toolchains.json",
            ".github/workflows/kicad-template.yml",
            "pyproject.toml",
            "AGENTS.md",
            "LICENSE.md",
            "tools/README.md",
        ):
            with self.subTest(path=path):
                plan = plan_paths(ROOT, (path,))
                self.assertEqual(plan.scope, "full")
                self.assertEqual(plan.projects, ALL_IDS)

    def test_configured_catalog_path_is_global_even_if_moved_under_docs(self) -> None:
        registry = load_registry(ROOT)
        catalogs = registry.catalogs.model_copy(update={"parts": "docs/parts.md"})
        with patch(
            "kicad_tooling.hwrepo.impact.load_registry",
            return_value=registry.model_copy(
                update={"catalogs": catalogs},
            ),
        ):
            plan = plan_paths(ROOT, ("docs/parts.md",))
        self.assertEqual(plan.scope, "full")
        self.assertEqual(plan.projects, ALL_IDS)

    def test_unknown_or_unowned_deleted_paths_fall_back_to_full(self) -> None:
        for path in (
            "projects/deleted-board/kicad/deleted-board.kicad_pcb",
            "examples/libraries/unowned/part.kicad_sym",
            "examples/projects/controller-old/kicad/board.kicad_pcb",
        ):
            with self.subTest(path=path):
                plan = plan_paths(ROOT, (path,))
                self.assertEqual(plan.scope, "full")
                self.assertEqual(plan.projects, ALL_IDS)
                self.assertTrue(any("No declared owner" in reason for reason in plan.reasons))

    def test_unknown_markdown_is_not_mistaken_for_documentation_scope(self) -> None:
        for path in (
            "mystery/README.md",
            "projects/deleted-board/docs/design.md",
            "examples/libraries/unowned/PROVENANCE.md",
        ):
            with self.subTest(path=path):
                plan = plan_paths(ROOT, (path,))
                self.assertEqual(plan.scope, "full")
                self.assertEqual(plan.projects, ALL_IDS)
                self.assertTrue(
                    any("No declared documentation owner" in reason for reason in plan.reasons)
                )

    def test_invalid_changed_path_and_empty_diff_fail_closed(self) -> None:
        for path in ("", "../escape.kicad_pcb", "/tmp/out.kicad_pcb", "C:\\temp\\board.kicad_pcb"):
            with self.subTest(path=path):
                plan = plan_paths(ROOT, (path,))
                self.assertEqual(plan.scope, "full")
                self.assertEqual(plan.projects, ALL_IDS)
                self.assertTrue(any("Unsafe" in reason for reason in plan.reasons))
        self.assertEqual(plan_paths(ROOT, ()).scope, "full")

    def test_order_and_duplicate_paths_do_not_change_selection(self) -> None:
        one = "examples/projects/controller/kicad/controller.kicad_pcb"
        two = "examples/products/status-indicator-system/product.json"
        plan = plan_paths(ROOT, (two, one, one))
        self.assertEqual(plan.scope, "focused")
        self.assertEqual(plan.projects, tuple(sorted((*PRODUCT_IDS, "controller"))))
        self.assertEqual(plan.changed_paths, tuple(sorted((one, two))))


if __name__ == "__main__":
    unittest.main()
