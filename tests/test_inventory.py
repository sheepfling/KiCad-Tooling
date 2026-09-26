"""Read-only newcomer inventory and human/agent output contracts."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.inventory import inventory
from kicad_tooling.hwrepo.models import ProductIndex, ProjectDiscovery, ProjectKind
from kicad_tooling.hwrepo.scaffold import new_project
from kicad_tooling.template import main as template_main
from tests.support import reference_root


class InventoryTests(unittest.TestCase):
    def test_reference_inventory_exposes_usable_selection_names(self) -> None:
        report = inventory(reference_root())
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertIn("controller", {project.id for project in report.projects})
        self.assertEqual(
            next(group.project_ids for group in report.products
                 if group.id == "status-indicator-system"),
            ("arduino-uno-status-led", "raspberry-pi-status-led", "status-indicator-wiring",
             "status-indicator-harness-interface"),
        )
        self.assertEqual(
            {project.id for project in report.projects if "status-led" in project.tags},
            set(next(group.project_ids for group in report.tags if group.id == "status-led")),
        )
        self.assertEqual({toolchain.id for toolchain in report.toolchains},
                         {"kicad-10.0.0", "kicad-10.0.5"})
        self.assertTrue(all(project.readiness == "INPUTS_PRESENT" for project in report.projects))
        self.assertTrue(all("kicad_tooling.verify --project" in project.next_command
                            for project in report.projects))

    def test_empty_adopted_registry_and_incomplete_scaffold_are_not_called_validated(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kicad-inventory-") as temporary:
            root = Path(temporary)
            shutil.copytree(reference_root() / "catalog", root / "catalog")
            shutil.copytree(reference_root() / "templates", root / "templates")
            (root / "projects").mkdir()
            discovery_path = root / "catalog/projects.json"
            discovery = read_model(discovery_path, ProjectDiscovery)
            write_model(discovery_path, discovery.model_copy(update={"project_roots": ("projects",)}))
            write_model(root / "catalog/products.json", ProductIndex(schema_version="1", products=()))
            empty = inventory(root)
            self.assertEqual(empty.status, "PASS", empty.issues)
            self.assertEqual(empty.projects, ())
            self.assertEqual(empty.products, ())
            self.assertIn("No live projects", empty.next_actions[0])

            scaffold = new_project(root, "battery-board", ProjectKind.PCB, "kicad-10.0.5")
            self.assertEqual(scaffold.status, "PASS", scaffold.issues)
            self.assertIn("kicad_tooling.verify --project battery-board", scaffold.next_step)
            report = inventory(root)
            self.assertEqual(report.status, "PASS", report.issues)
            project = report.projects[0]
            self.assertEqual(project.readiness, "NEEDS_INPUTS")
            self.assertIn("projects/battery-board/kicad/battery-board.kicad_pro",
                          project.missing_inputs)
            self.assertIn("kicad_tooling.verify --project battery-board", project.next_command)
            (root / "projects/battery-board/kicad").rmdir()
            missing_root = inventory(root)
            self.assertIn("projects/battery-board/kicad",
                          missing_root.projects[0].missing_inputs)

    def test_invalid_registry_returns_actionable_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kicad-inventory-") as temporary:
            root = Path(temporary)
            shutil.copytree(reference_root() / "catalog", root / "catalog")
            shutil.copytree(reference_root() / "examples/products", root / "examples/products")
            shutil.copytree(reference_root() / "examples/projects", root / "examples/projects")
            path = root / "examples/projects/controller/project.json"
            path.write_text("{broken JSON", encoding="utf-8")
            report = inventory(root)
            self.assertEqual(report.status, "FAIL")
            self.assertEqual(report.issues[0].code, "INVENTORY_INPUT")
            self.assertIn("project.json", report.issues[0].message)

    def test_invalid_product_membership_fails_with_source_location(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kicad-inventory-") as temporary:
            root = Path(temporary)
            shutil.copytree(reference_root() / "catalog", root / "catalog")
            shutil.copytree(reference_root() / "examples/products", root / "examples/products")
            shutil.copytree(reference_root() / "examples/projects", root / "examples/projects")
            index_path = root / "catalog/products.json"
            index = read_model(index_path, ProductIndex)
            broken = index.products[0].model_copy(update={"project_ids": ("unknown-board",)})
            write_model(index_path, index.model_copy(update={"products": (broken,)}))
            report = inventory(root)
            self.assertEqual(report.status, "FAIL")
            self.assertIn("unknown-board", report.issues[0].message)
            self.assertIn("catalog/products.json", report.issues[0].message)

    def test_cli_keeps_json_structured_and_text_scannable(self) -> None:
        root = reference_root()
        with (
            patch.object(sys, "argv", ["kicad_tooling.template", "list", "--root", str(root)]),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(template_main(), 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["lane"], "TEMPLATE_INVENTORY")
        self.assertFalse(payload["build_authorized"])
        self.assertEqual(payload["status"], "PASS")
        self.assertIn("products", payload["projects"][0])
        with (
            patch.object(sys, "argv", ["kicad_tooling.template", "list", "--root", str(root),
                                       "--format", "text"]),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(template_main(), 0)
        self.assertIn("Repository inventory: PASS", output.getvalue())
        self.assertIn("Products (1):", output.getvalue())
        self.assertIn("Input presence is not validation", output.getvalue())


if __name__ == "__main__":
    unittest.main()
