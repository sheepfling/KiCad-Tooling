"""Real temporary checkouts exercise the same layout boundary as CLI and MCP."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kicad_tooling.hwrepo.discovery import (
    load_config,
    load_registry,
    manifest_paths,
    project_destination,
)
from kicad_tooling.hwrepo.importing import import_project
from kicad_tooling.hwrepo.inventory import inventory
from kicad_tooling.hwrepo.layout import layout
from kicad_tooling.hwrepo.mcp_files import (
    artifact_path,
    preview_project_edit,
    project_file_path,
    read_project_file,
)
from kicad_tooling.hwrepo.models import ProjectKind
from kicad_tooling.hwrepo.rescue import selected_manifest
from kicad_tooling.hwrepo.scaffold import new_project

SOURCE = Path(__file__).resolve().parents[1]


def write_json(root: Path, name: str, value: object) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class LayoutTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.config = self.root / "kicad-tooling.toml"
        self.config.write_text("""schema_version = "1"
[layout]
discovery = "policy/discovery.json"
products = "policy/products.json"
team_policy = "policy/team-policy.json"
templates = "starter"
workflow_docs = "handbook"
new_project_root = "hardware/team-a"
product_roots = ["assemblies"]
library_roots = ["shared/cad"]
""")
        self.discovery = {
            "schema_version": "1",
            "project_roots": ["hardware"],
            "project_depth": 2,
            "catalogs": {
                key: f"policy/{key}.json"
                for key in (
                    "parts",
                    "interfaces",
                    "libraries",
                    "toolchains",
                    "release_policies",
                )
            },
        }
        write_json(self.root, "policy/discovery.json", self.discovery)
        write_json(self.root, "policy/products.json", {"schema_version": "1", "products": []})
        write_json(
            self.root,
            "policy/toolchains.json",
            {
                "schema_version": "1",
                "toolchains": [
                    {
                        "id": "approved",
                        "kicad_version": "10.0.0",
                        "image": "example/kicad@sha256:" + "0" * 64,
                        "desktop_edit_policy": "reviewed",
                        "installer_source": "synthetic fixture",
                        "migration_policy": "review before use",
                    }
                ],
            },
        )
        self.manifest = {
            "schema_version": "1",
            "id": "REPLACE-WITH-PROJECT-ID",
            "kind": "pcb",
            "status": "engineering",
            "assurance_profile": "development",
            "toolchain_id": "approved",
            "project": "kicad/REPLACE-WITH-PROJECT-ID.kicad_pro",
            "source_roots": ["kicad"],
            "required_inputs": [],
            "component_identity": {"required": False, "part_ids": []},
        }
        write_json(self.root, "starter/pcb-project-config.example.json", self.manifest)
        write_json(
            self.root,
            "starter/project-tests/pcb.json",
            {
                "schema_version": "1",
                "validation": {
                    "kind": "pcb",
                    "components": {},
                    "nets": {},
                    "expected_ignored_checks": {"erc": [], "drc": []},
                },
            },
        )
        (self.root / "handbook").mkdir()
        (self.root / "handbook/START_HERE.md").write_text("# Custom onboarding\n")

    def create(self, project_id: str = "board") -> Path:
        report = new_project(self.root, project_id, ProjectKind.PCB, "approved")
        self.assertEqual("PASS", report.status, report.issues)
        self.assertEqual(f"hardware/team-a/{project_id}", report.directory)
        return self.root / report.directory

    def test_nested_scaffold_inventory_and_mcp_source_share_identity(self) -> None:
        island = self.create()
        report = inventory(self.root)
        self.assertEqual("PASS", report.status, report.issues)
        self.assertEqual("hardware/team-a/board/project.json", report.projects[0].manifest)
        self.assertEqual(island / "project.json", selected_manifest(self.root, "board"))
        self.assertEqual(island / "README.md", project_file_path(self.root, "board", "README.md"))
        self.assertEqual(
            island / "build/receipt.json",
            artifact_path(
                self.root,
                "hardware/team-a/board/build/receipt.json",
            ),
        )
        for name in (
            "hardware/team-a/unregistered/build/file.txt",
            "hardware/build/file.txt",
            "hardware/team-a/board/build/restores/source.json",
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                artifact_path(self.root, name)

    def test_mcp_product_receipts_follow_the_configured_index(self) -> None:
        write_json(
            self.root,
            "policy/products.json",
            {
                "schema_version": "1",
                "products": [
                    {
                        "id": "robot",
                        "path": "assemblies/robot/product.json",
                        "project_ids": [],
                    }
                ],
            },
        )
        self.assertEqual(
            self.root / "assemblies/robot/build/result.json",
            artifact_path(
                self.root,
                "assemblies/robot/build/result.json",
            ),
        )
        with self.assertRaises(ValueError):
            artifact_path(self.root, "assemblies/unknown/build/result.json")

    def test_non_json_toml_scalars_produce_structured_failure(self) -> None:
        self.config.write_text("schema_version = 2026-09-25\n")
        report = inventory(self.root)
        self.assertEqual("FAIL", report.status)
        self.assertIn("kicad-tooling.toml", str(report.issues))

    def test_loaded_project_retains_explicit_new_major_profile(self) -> None:
        island = self.create()
        path = self.root / "policy/toolchains.json"
        catalog = json.loads(path.read_text())
        catalog["toolchains"][0].update(kicad_version="11.0.0", cli_profile="kicad-10")
        path.write_text(json.dumps(catalog))
        config = load_config(self.root, island / "project.json")
        self.assertEqual("11.0.0", config.kicad_version)
        self.assertEqual("kicad-10", config.cli_profile)

    def test_import_preview_and_write_use_the_same_nested_destination(self) -> None:
        source = self.root / "incoming"
        source.mkdir()
        (source / "sample.kicad_pro").write_text("{}")
        (source / "sample.kicad_sch").write_text("(kicad_sch)")
        (source / "sample.kicad_pcb").write_text("(kicad_pcb)")
        preview = import_project(
            self.root, source / "sample.kicad_pro", "imported", "approved", True
        )
        self.assertEqual("PASS", preview.status, preview.issues)
        self.assertEqual("hardware/team-a/imported", preview.directory)
        self.assertFalse((self.root / preview.directory).exists())
        applied = import_project(self.root, source / "sample.kicad_pro", "imported", "approved")
        self.assertEqual("PASS", applied.status, applied.issues)
        self.assertEqual(preview.directory, applied.directory)
        self.assertEqual("imported", load_registry(self.root).projects[0].id)

    def test_mcp_reads_and_validates_a_relocated_check_contract(self) -> None:
        island = self.create()
        (island / "quality").mkdir()
        (island / "tests/contract.json").rename(island / "quality/checks.json")
        manifest_path = island / "project.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["checks"] = "quality/checks.json"
        manifest_path.write_text(json.dumps(manifest))
        content = read_project_file(self.root, "board", "quality/checks.json")
        with self.assertRaises(ValueError):
            preview_project_edit(
                self.root,
                "board",
                "quality/checks.json",
                content.sha256,
                '"kind": "pcb"',
                '"kind": "schematic"',
            )
        (island / "quality/checks.json").write_text("{broken")
        self.assertEqual(
            island / "quality/checks.json",
            project_file_path(
                self.root,
                "board",
                "quality/checks.json",
            ),
        )

    def test_selected_repair_does_not_parse_malformed_peer(self) -> None:
        island = self.create()
        other = self.create("broken")
        (other / "project.json").write_text("{broken")
        self.assertEqual(island / "project.json", selected_manifest(self.root, "board"))
        self.assertEqual(
            other / "project.json", project_file_path(self.root, "broken", "project.json")
        )
        with self.assertRaises(ValueError):
            load_registry(self.root)

    def test_duplicate_ids_and_overlapping_roots_are_rejected(self) -> None:
        self.create()
        write_json(
            self.root, "hardware/team-b/board/project.json", {**self.manifest, "id": "board"}
        )
        with self.assertRaisesRegex(ValueError, "Duplicate project id"):
            load_registry(self.root)
        write_json(
            self.root,
            "policy/discovery.json",
            {
                **self.discovery,
                "project_roots": ["hardware", "hardware/team-a"],
            },
        )
        with self.assertRaisesRegex(ValueError, "overlap"):
            manifest_paths(self.root)

    def test_creation_depth_and_existing_island_boundaries(self) -> None:
        write_json(self.root, "policy/discovery.json", {**self.discovery, "project_depth": 1})
        self.assertEqual(
            "FAIL", new_project(self.root, "board", ProjectKind.PCB, "approved").status
        )
        self.assertFalse((self.root / "hardware").exists())
        write_json(self.root, "policy/discovery.json", self.discovery)
        write_json(self.root, "hardware/team-a/project.json", {**self.manifest, "id": "team-a"})
        with self.assertRaisesRegex(ValueError, "inside an existing"):
            project_destination(self.root, "board")

    def test_unknown_settings_traversal_and_symlink_escape_are_rejected(self) -> None:
        for content in (
            '[layout]\nnew_projects_root="typo"\n',
            '[layout]\ndiscovery="../outside.json"\n',
            '[layout]\nnew_project_root=".git/data"\n',
            '[layout]\ndiscovery="/absolute.json"\n',
        ):
            self.config.write_text(content)
            with self.subTest(content=content), self.assertRaises(ValueError):
                layout(self.root)
        self.config.write_text('[layout]\ndiscovery="linked/discovery.json"\n')
        with tempfile.TemporaryDirectory() as outside:
            (self.root / "linked").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "Linked"):
                layout(self.root)

    def test_default_layout_and_one_level_discovery_remain_unchanged(self) -> None:
        self.config.unlink()
        self.assertEqual("catalog/projects.json", layout(self.root).discovery)
        write_json(
            self.root,
            "catalog/projects.json",
            {
                **self.discovery,
                "project_roots": ["projects"],
                "project_depth": 1,
            },
        )
        write_json(self.root, "projects/team/board/project.json", {**self.manifest, "id": "board"})
        self.assertEqual((), manifest_paths(self.root))
        write_json(self.root, "projects/board/project.json", {**self.manifest, "id": "board"})
        self.assertEqual("board", load_registry(self.root).projects[0].id)

    def test_cli_inventory_from_external_cwd(self) -> None:
        self.create()
        environment = os.environ.copy()
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling",
                "template",
                "list",
                "--format",
                "json",
            ],
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "hardware/team-a/board/project.json",
            json.loads(result.stdout)["projects"][0]["manifest"],
        )

    def test_mcp_uses_same_catalog_and_workflow_docs(self) -> None:
        try:
            from kicad_tooling.hwrepo.mcp_server import create_server
        except ImportError:
            self.skipTest("MCP extra is not installed")
        self.create()
        server = create_server(self.root)

        # Use the SDK dispatch surface, not a second implementation of discovery.
        async def exercise() -> None:
            result = await server.call_tool("list_projects", {})
            encoded = str(result)
            self.assertIn("hardware/team-a/board/project.json", encoded)
            document = await server.call_tool("read_document", {"name": "start-here"})
            self.assertIn("Custom onboarding", str(document))

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
