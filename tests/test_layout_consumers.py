"""Configured repository layouts stay authoritative across shared workflow services."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kicad_tooling.hwrepo.generation import expected_outputs, generate, snapshot
from kicad_tooling.hwrepo.impact import plan_paths
from kicad_tooling.hwrepo.inventory import inventory
from kicad_tooling.hwrepo.models import ReleaseClass, ReleaseManifest, ReleaseStatus
from kicad_tooling.hwrepo.part_picker import _snapshot, _verify_snapshot
from kicad_tooling.hwrepo.parts_workflow import input_hashes
from kicad_tooling.hwrepo.product import load_repository
from kicad_tooling.hwrepo.project_tests import run_tests
from kicad_tooling.hwrepo.release import load_release_repository
from kicad_tooling.hwrepo.releasing import resolve_variants
from kicad_tooling.hwrepo.selection import ProjectSelector, resolve_project_ids

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class LayoutConsumersTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="tooling-layout-consumers-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.discovery = "policy/discovery.json"
        self.products = "policy/assemblies.json"
        self.project = "hardware/boards/team/board"
        self.product = "hardware/assemblies/device"
        self.write(
            "kicad-tooling.toml",
            """[layout]
discovery = "policy/discovery.json"
products = "policy/assemblies.json"
templates = "policy/templates"
workflow_docs = "handbook/workflow"
new_project_root = "hardware/boards/team"
product_roots = ["hardware/assemblies"]
library_roots = ["cad/libraries"]
""",
        )
        self.write_json(
            self.discovery,
            {
                "schema_version": "1",
                "project_roots": ["hardware/boards"],
                "project_depth": 2,
                "catalogs": {
                    name: f"policy/{name}.json"
                    for name in (
                        "parts",
                        "interfaces",
                        "libraries",
                        "toolchains",
                        "release_policies",
                    )
                },
            },
        )
        self.write_json(
            self.products,
            {
                "schema_version": "1",
                "products": [
                    {
                        "id": "device",
                        "path": f"{self.product}/product.json",
                        "project_ids": ["board"],
                    }
                ],
            },
        )
        self.write_json(
            "policy/toolchains.json",
            {
                "schema_version": "1",
                "toolchains": [
                    {
                        "id": "kicad",
                        "kicad_version": "10.0.0",
                        "image": "kicad:10",
                        "desktop_edit_policy": "Save before checking",
                        "installer_source": "local",
                        "migration_policy": "Review migrations",
                    }
                ],
            },
        )
        self.write_json(
            "policy/parts.json",
            {
                "schema_version": "1",
                "parts": [
                    {
                        "id": "resistor",
                        "revision": "A",
                        "description": "Test resistor",
                        "part_class": "resistor",
                        "unit": "each",
                        "manufacturer": "Fixture",
                        "mpn": "R1",
                        "datasheet_url": "https://example.test/r1",
                        "lifecycle": "test",
                        "status": "not_for_manufacture",
                    }
                ],
            },
        )
        for name, collection in (
            ("interfaces", "interfaces"),
            ("libraries", "libraries"),
            ("release_policies", "policies"),
        ):
            self.write_json(f"policy/{name}.json", {"schema_version": "1", collection: []})
        self.write_json(
            f"{self.project}/project.json",
            {
                "id": "board",
                "kind": "pcb",
                "status": "training_fixture",
                "assurance_profile": "training",
                "toolchain_id": "kicad",
                "project": "pcb/board.kicad_pro",
                "source_roots": ["pcb"],
                "required_inputs": ["pcb/board.kicad_pro"],
                "tags": ["demo"],
                "component_identity": {"required": True, "part_ids": ["resistor"]},
            },
        )
        self.write(f"{self.project}/pcb/board.kicad_pro", "{}\n")
        self.write_json(
            f"{self.project}/tests/contract.json",
            {
                "validation": {
                    "kind": "pcb",
                    "components": {
                        "R1": {"value": "1k", "footprint": "R:0603", "part_id": "resistor"}
                    },
                    "nets": {},
                    "expected_ignored_checks": {"erc": [], "drc": []},
                }
            },
        )
        self.write_json(
            f"{self.product}/product.json",
            {
                "schema_version": "1",
                "id": "device",
                "revision": "A",
                "maturity": "training",
                "root_assembly": "board-assembly",
                "assemblies": [
                    {
                        "id": "board-assembly",
                        "revision": "A",
                        "kind": "built",
                        "project_id": "board",
                        "members": [{"ref": "R1", "item": "resistor", "quantity": 1}],
                    }
                ],
                "terminals": [],
                "connections": [],
                "variants": [
                    {
                        "id": "standard",
                        "revision": "A",
                        "exclude": [],
                    }
                ],
                "evidence": [],
                "harnesses": [],
                "mechanical": [],
                "blocking_issues": [],
            },
        )
        self.write("handbook/workflow/review.md", "# Review\n")
        self.write("policy/templates/template.txt", "authored template\n")
        self.write("cad/libraries/fixture.txt", "authored library\n")

    def write(self, name: str, text: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_json(self, name: str, document: object) -> None:
        self.write(name, json.dumps(document) + "\n")

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        return subprocess.run(
            (sys.executable, "-I", "-B", "-m", "kicad_tooling", *args),
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_inventory_selection_and_release_use_configured_catalogs(self) -> None:
        report = inventory(self.root)
        self.assertEqual("PASS", report.status, report.issues)
        self.assertEqual(("board",), tuple(item.id for item in report.projects))
        self.assertEqual(("device",), report.projects[0].products)
        self.assertEqual(
            ("board",), resolve_project_ids(self.root, ProjectSelector(product_ids=("device",)))
        )
        variants = resolve_variants(self.root, ("device:standard",))
        self.assertEqual("A", variants[0].product_revision)
        candidate = ReleaseManifest(
            release_id="review",
            release_class=ReleaseClass.ENGINEERING_REVIEW,
            status=ReleaseStatus.CANDIDATE,
            source_commit="0" * 40,
            toolchain_id="kicad",
            variants=variants,
            libraries=(),
            interfaces=(),
            artifacts=(),
        )
        repository = load_release_repository(self.root, candidate)
        self.assertEqual((), repository.issues)
        self.assertEqual(("device",), tuple(item.id for item in repository.products))
        result = self.cli("template", "list", "--format", "json")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(
            self.project + "/project.json", json.loads(result.stdout)["projects"][0]["manifest"]
        )
        self.assertFalse((self.root / "catalog").exists())

    def test_generation_cli_and_service_use_custom_product_destination(self) -> None:
        outputs = expected_outputs(self.root, ("board",))
        bom = f"{self.product}/build/standard.bom.csv"
        self.assertIn(bom, outputs)
        self.assertIn(b"resistor", outputs[bom])
        result = self.cli("hardware", "generate", "--product", "device", "--format", "json")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)["build_authorized"])
        self.assertEqual(outputs[bom], (self.root / bom).read_bytes())
        isolated = self.root / "build/separate"
        generate(self.root, output=isolated, selected_project_ids=("board",))
        self.assertEqual(outputs[bom], (isolated / bom).read_bytes())

    def test_custom_product_roots_still_detect_unregistered_and_deep_products(self) -> None:
        original = (self.root / self.product / "product.json").read_text()
        self.write("hardware/assemblies/orphan/product.json", original)
        repository = load_repository(self.root)
        self.assertIn("PRODUCT_DISCOVERY", {issue.code for issue in repository.issues})
        (self.root / "hardware/assemblies/orphan/product.json").unlink()
        self.write_json(
            self.products,
            {
                "schema_version": "1",
                "products": [
                    {
                        "id": "device",
                        "path": "hardware/assemblies/group/device/product.json",
                        "project_ids": ["board"],
                    }
                ],
            },
        )
        self.write("hardware/assemblies/group/device/product.json", original)
        repository = load_repository(self.root)
        self.assertIn("PRODUCT_LOAD", {issue.code for issue in repository.issues})
        self.assertTrue(any("direct child" in issue.message for issue in repository.issues))

    def test_product_catalog_cannot_escape_configured_roots(self) -> None:
        original = (self.root / self.product / "product.json").read_text()
        for invalid in ("hardware/assemblies-evil/device/product.json", "../outside.json"):
            with self.subTest(path=invalid):
                self.write_json(
                    self.products,
                    {
                        "schema_version": "1",
                        "products": [
                            {
                                "id": "device",
                                "path": invalid,
                                "project_ids": ["board"],
                            }
                        ],
                    },
                )
                if ".." not in invalid:
                    self.write(invalid, original)
                self.assertIn(
                    "PRODUCT_LOAD", {item.code for item in load_repository(self.root).issues}
                )

    @unittest.skipIf(os.name == "nt", "POSIX symbolic-link boundary")
    def test_product_and_snapshot_reject_linked_source(self) -> None:
        path = self.root / self.product / "product.json"
        path.rename(path.with_name("real.json"))
        path.symlink_to("real.json")
        self.assertIn("PRODUCT_LOAD", {item.code for item in load_repository(self.root).issues})
        path.unlink()
        path.with_name("real.json").rename(path)
        (self.root / "cad/libraries/link.txt").symlink_to(self.root / self.discovery)
        with self.assertRaisesRegex(ValueError, "Linked repository path"):
            snapshot(self.root, self.root / "build/unsafe")
        self.assertFalse((self.root / "build/unsafe").exists())

    def test_impact_maps_custom_catalogs_docs_and_nested_project_sources(self) -> None:
        for name in (self.discovery, self.products, "kicad-tooling.toml"):
            with self.subTest(path=name):
                report = plan_paths(self.root, (name,))
                self.assertEqual("full", report.scope)
                self.assertIn("Shared workflow or policy", report.reasons[0])
        self.assertEqual("docs", plan_paths(self.root, ("handbook/workflow/review.md",)).scope)
        report = plan_paths(self.root, (f"{self.project}/pcb/board.kicad_pro",))
        self.assertEqual("focused", report.scope)
        self.assertEqual(("board",), report.projects)

    def test_parts_inputs_bind_layout_changes_and_missing_configuration(self) -> None:
        before = input_hashes(self.root, "board", None)
        selection = _snapshot(self.root, "board")
        self.assertIn(self.discovery, before)
        self.assertIn("kicad-tooling.toml", before)
        self.assertEqual(before["kicad-tooling.toml"], selection["kicad-tooling.toml"])
        with (self.root / "kicad-tooling.toml").open("a") as stream:
            stream.write("# reviewed layout changed\n")
        self.assertNotEqual(before, input_hashes(self.root, "board", None))
        with self.assertRaisesRegex(ValueError, "kicad-tooling.toml"):
            _verify_snapshot(self.root, "board", selection)
        # A default-layout checkout also binds configuration absence before a later opt-in.
        (self.root / "kicad-tooling.toml").unlink()
        self.write("catalog/projects.json", (self.root / self.discovery).read_text())
        absent = _snapshot(self.root, "board")
        self.assertIsNone(absent["kicad-tooling.toml"])
        self.assertNotIn("kicad-tooling.toml", input_hashes(self.root, "board", None))
        self.write("kicad-tooling.toml", "[layout]\n")
        with self.assertRaisesRegex(ValueError, "kicad-tooling.toml"):
            _verify_snapshot(self.root, "board", absent)

    def test_snapshot_binds_all_configured_source_scopes(self) -> None:
        for command in (
            ("init",),
            ("add", "."),
            (
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.test",
                "commit",
                "-m",
                "Fixture",
            ),
        ):
            result = subprocess.run(
                ("git", *command), cwd=self.root, capture_output=True, text=True, check=False
            )
            self.assertEqual(0, result.returncode, result.stderr)
        report = snapshot(self.root, self.root / "build/review")
        for name in (
            "kicad-tooling.toml",
            self.discovery,
            self.products,
            f"{self.project}/project.json",
            f"{self.product}/product.json",
            "policy/templates/template.txt",
            "handbook/workflow/review.md",
            "cad/libraries/fixture.txt",
        ):
            with self.subTest(path=name):
                self.assertEqual(
                    hashlib.sha256((self.root / name).read_bytes()).hexdigest(),
                    report.sources_sha256[name],
                )
        self.assertFalse(report.build_authorized)
        self.assertEqual("NOT_RUN", report.checks["kicad"])

    def test_product_unittest_suite_is_discovered_through_custom_index(self) -> None:
        self.write(
            f"{self.product}/tests/test_product.py",
            """import unittest
class ProductTests(unittest.TestCase):
    def test_marker(self):
        self.assertEqual(2, 1 + 1)
""",
        )
        report = run_tests(self.root, ("board",))
        self.assertEqual("PASS", report.status)
        self.assertEqual({"product-device"}, set(report.commands))
        self.assertIn("Ran 1 test", report.commands["product-device"].stderr)


if __name__ == "__main__":
    unittest.main()
