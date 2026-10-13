"""MCP import previews, path boundaries, and import workflow."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import ProjectManifest
from tests.mcp_test_support import McpTestCase, snapshot

pytestmark = [pytest.mark.slow, pytest.mark.template_checkout]


class McpTests(McpTestCase):
    async def test_external_preview_requires_startup_root_and_preserves_source_and_checkout(
        self,
    ) -> None:
        before_root, before_source = snapshot(self.root), snapshot(self.source)
        async with Client(create_server(self.root), mode="legacy") as client:
            denied = await client.call_tool("preview_import", self.import_arguments())
            self.assertTrue(denied.is_error, denied.content)
            self.assertIn("--import-root", self.text(denied))
        async with Client(
            create_server(self.root, import_roots=(self.source,)),
            mode="legacy",
        ) as client:
            data = self.structured(
                await client.call_tool("preview_import", self.import_arguments())
            )
            self.assertEqual(data["status"], "PASS", data["issues"])
            self.assertTrue(data["dry_run"])
            self.assertTrue(data["review_required"])
            self.assertIn(self.project.name, data["copied_sha256"])
            self.assertFalse((self.root / data["directory"]).exists())
        self.assertEqual(snapshot(self.root), before_root)
        self.assertEqual(snapshot(self.source), before_source)

    async def test_checkout_preview_accepts_source_without_enabling_writes(self) -> None:
        source = self.root / "incoming"
        shutil.copytree(self.source, source)
        before = snapshot(self.root)
        async with Client(create_server(self.root), mode="legacy") as client:
            data = self.structured(
                await client.call_tool(
                    "preview_import",
                    self.import_arguments(Path("incoming") / self.project.name),
                )
            )
            self.assertEqual(data["status"], "PASS", data["issues"])
            self.assertTrue(data["dry_run"])
        self.assertEqual(snapshot(self.root), before)

    async def test_import_symlink_and_parent_traversal_do_not_expand_authorized_roots(self) -> None:
        linked = self.root / "linked-input"
        try:
            linked.symlink_to(self.source, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink creation unavailable")
        before = snapshot(self.root)
        async with Client(create_server(self.root), mode="legacy") as client:
            for source in (
                linked / self.project.name,
                self.root / ".." / self.source.name / self.project.name,
            ):
                with self.subTest(source=str(source)):
                    denied = await client.call_tool("preview_import", self.import_arguments(source))
                    self.assertTrue(denied.is_error, denied.content)
        self.assertEqual(snapshot(self.root), before)

    async def test_write_mode_scaffolds_without_overwriting_or_accepting_invalid_ids(self) -> None:
        arguments = {"project_id": "new-board", "kind": "pcb", "toolchain_id": "kicad-10.0.5"}
        async with Client(create_server(self.root, allow_writes=True), mode="legacy") as client:
            created = self.structured(await client.call_tool("new_project", arguments))
            self.assertEqual(created["status"], "PASS", created["issues"])
            island = self.root / created["directory"]
            manifest = read_model(island / "project.json", ProjectManifest)
            self.assertEqual(manifest.id, "new-board")
            self.assertEqual(manifest.assurance_profile, "development")
            self.assertFalse((island / manifest.project).exists())
            notes = island / "docs/README.md"
            notes.write_text("Preserve the contributor's design notes.\n", encoding="utf-8")
            before = snapshot(self.root)
            repeated = self.structured(await client.call_tool("new_project", arguments))
            self.assertEqual(repeated["status"], "FAIL")
            for update in (
                {"project_id": "../escape"},
                {"project_id": "unknown-toolchain", "toolchain_id": "unknown"},
                {"project_id": "invalid-kind", "kind": "other"},
            ):
                with self.subTest(update=update):
                    rejected = await client.call_tool("new_project", arguments | update)
                    self.assertTrue(
                        rejected.is_error or self.structured(rejected)["status"] == "FAIL",
                        rejected.content,
                    )
            self.assertEqual(snapshot(self.root), before)
            self.assertFalse((self.base / "escape").exists())

    async def test_authorized_import_copies_source_and_keeps_review_required(self) -> None:
        before_source = snapshot(self.source)
        async with Client(
            create_server(
                self.root,
                allow_writes=True,
                import_roots=(self.source,),
            ),
            mode="legacy",
        ) as client:
            data = self.structured(
                await client.call_tool("import_project", self.import_arguments())
            )
            self.assertEqual(data["status"], "PASS", data["issues"])
            self.assertFalse(data["dry_run"])
            self.assertTrue(data["review_required"])
            island = self.root / data["directory"]
            for name in before_source:
                self.assertEqual(
                    (island / "kicad" / name).read_bytes(), (self.source / name).read_bytes()
                )
            listed = self.structured(await client.call_tool("list_projects"))
            self.assertIn("incoming-board", {project["id"] for project in listed["projects"]})
        self.assertEqual(snapshot(self.source), before_source)

    async def test_import_triage_receipt_source_edit_and_recheck_sequence(self) -> None:
        async with Client(
            create_server(
                self.root,
                import_roots=(self.source,),
                allow_writes=True,
                allow_edits=True,
                allow_checks=True,
            ),
            mode="legacy",
        ) as client:
            scanned = self.structured(
                await client.call_tool(
                    "scan_imports",
                    {
                        "source_directory": str(self.source),
                        "toolchain_id": "kicad-10.0.5",
                    },
                )
            )
            self.assertEqual(len(scanned["candidates"]), 1)
            triage = self.structured(
                await client.call_tool("diagnose_import", self.import_arguments())
            )
            self.assertEqual(triage["status"], "PASS")
            receipt = Path(triage["run_directory"]).relative_to(self.root).as_posix()
            listing = self.structured(
                await client.call_tool("list_artifacts", {"directory": receipt})
            )
            self.assertIn(
                receipt + "/diagnosis.json", {item["path"] for item in listing["entries"]}
            )
            artifact = self.structured(
                await client.call_tool(
                    "read_artifact",
                    {
                        "path": receipt + "/diagnosis.json",
                    },
                )
            )
            self.assertEqual(json.loads(artifact["text"])["project_id"], "incoming-board")
            imported = self.structured(
                await client.call_tool("import_project", self.import_arguments())
            )
            self.assertEqual(imported["status"], "PASS")
            source = self.structured(
                await client.call_tool(
                    "read_project_file",
                    {
                        "project_id": "incoming-board",
                        "path": "docs/README.md",
                    },
                )
            )
            old = source["text"].splitlines()[0]
            edit = {
                "project_id": "incoming-board",
                "path": "docs/README.md",
                "expected_sha256": source["sha256"],
                "old_text": old,
                "new_text": old + " (review in progress)",
            }
            preview = self.structured(await client.call_tool("preview_project_edit", edit))
            self.assertIn("review in progress", preview["diff"])
            self.assertEqual(source["sha256"], preview["before_sha256"])
            applied = self.structured(await client.call_tool("apply_project_edit", edit))
            self.assertEqual(applied["after_sha256"], preview["after_sha256"])
            self.assertEqual(applied["readback_sha256"], preview["after_sha256"])
            self.assertTrue(applied["checks_required"])
            stale = await client.call_tool("apply_project_edit", edit)
            self.assertTrue(stale.is_error)
            diagnosis = self.structured(
                await client.call_tool(
                    "diagnose_project",
                    {
                        "project_id": "incoming-board",
                    },
                )
            )
            self.assertEqual(diagnosis["status"], "NEEDS_WORK")
            self.assertTrue(any(row["severity"] == "BLOCKING" for row in diagnosis["findings"]))
            checked = self.structured(
                await client.call_tool(
                    "check_project",
                    {
                        "project_id": "incoming-board",
                    },
                )
            )
            # Portable structure can pass while diagnosis still requires electrical review.
            self.assertEqual(checked["status"], "PASS")
            self.assertFalse(checked["build_authorized"])
            # Importing and editing notes never fabricates the independent circuit contract.
            project = self.structured(
                await client.call_tool(
                    "get_project",
                    {
                        "project_id": "incoming-board",
                    },
                )
            )
            self.assertEqual(project["contract"]["validation"]["components"], {})
            self.assertEqual(project["contract"]["validation"]["nets"], {})
