"""Purchasing adapter type, file-kind, destination and concurrent-edit regressions."""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client
from mcp.types import TextContent

from kicad_tooling.hwrepo import mcp_files, mcp_parts, parts_workflow
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import McpPurchasingPreferencesResult, PurchasingPreferences
from tests import test_parts_workflow as fixture


class McpPartsSafetyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.fixture = fixture.PartsWorkflowTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.preferences = self.fixture.island / "docs/purchasing.json"
        self.summary = "build/native/controller/summary.json"

    def arguments(self, view_id: str = "safety-review"):
        return {"project_id": "controller", "view_id": view_id,
                "native_summary": self.summary}

    async def test_quantity_overrides_reject_coercion_before_receipt_creation(self) -> None:
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            for name in ("boards", "spare_percent", "spare_minimum"):
                for value in (True, "2", 2.0):
                    with self.subTest(name=name, value=value):
                        result = await client.call_tool("prepare_parts", self.arguments() | {name: value})
                        self.assertTrue(result.is_error, result.content)
                        self.assertFalse((self.root / "build/parts").exists())
            for name, value in (("boards", 0), ("spare_percent", 101), ("spare_minimum", -1)):
                with self.subTest(name=name, value=value):
                    result = await client.call_tool("prepare_parts", self.arguments() | {name: value})
                    self.assertTrue(result.is_error, result.content)
                    self.assertFalse((self.root / "build/parts").exists())

    async def test_tool_arguments_cannot_enable_capture_or_choose_a_destination(self) -> None:
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            tool = next(item for item in (await client.list_tools()).tools if item.name == "prepare_parts")
            for absent in ("allow_checks", "output", "cli", "root"):
                self.assertNotIn(absent, tool.input_schema["properties"])
            with patch("kicad_tooling.hwrepo.parts_workflow.prepare") as prepare:
                result = await client.call_tool("prepare_parts", {
                    "project_id": "controller", "view_id": "attempted-capture",
                    "allow_checks": True, "output": str(self.root.parent / "outside"),
                })
            self.assertTrue(result.is_error, result.content)
            prepare.assert_not_called()
            self.assertFalse((self.root / "build/parts").exists())
            self.assertFalse((self.root.parent / "outside").exists())

    @unittest.skipIf(os.name == "nt", "POSIX FIFO")
    def test_special_native_siblings_are_rejected_before_any_reader(self) -> None:
        for name in ("netlist.xml", "netlist.command.json", "erc.json", "drc.json"):
            with self.subTest(name=name):
                path = self.fixture.native / name
                original = path.read_bytes() if path.exists() else None
                path.unlink(missing_ok=True)
                os.mkfifo(path)
                try:
                    with patch("kicad_tooling.hwrepo.parts_workflow.prepare") as prepare:
                        with self.assertRaisesRegex(ValueError, "regular"):
                            mcp_parts.prepare_parts(self.root, "controller", "special-file", self.summary)
                        prepare.assert_not_called()
                    self.assertFalse((self.root / "build/parts").exists())
                finally:
                    path.unlink()
                    if original is not None:
                        path.write_bytes(original)

    @unittest.skipIf(os.name == "nt", "POSIX FIFO")
    def test_special_default_preferences_are_rejected_before_any_reader(self) -> None:
        os.mkfifo(self.preferences)
        with patch("kicad_tooling.hwrepo.parts_workflow.prepare") as prepare:
            with self.assertRaises(ValueError):
                mcp_parts.prepare_parts(self.root, "controller", "special-preferences", self.summary)
            prepare.assert_not_called()
        self.assertFalse((self.root / "build/parts").exists())

    def test_receipt_parent_symlinks_and_collisions_preserve_existing_files(self) -> None:
        parent = self.root / "build/parts"
        external = self.root.parent / "outside-parts"
        external.mkdir()
        marker = external / "keep.txt"
        marker.write_text("existing outside file", encoding="utf-8")
        try:
            parent.symlink_to(external, target_is_directory=True)
        except OSError as exc:
            self.skipTest(str(exc))
        with patch("kicad_tooling.hwrepo.parts_workflow.prepare") as prepare:
            with self.assertRaisesRegex(ValueError, "Linked"):
                mcp_parts.prepare_parts(self.root, "controller", "new-review", self.summary)
            prepare.assert_not_called()
        self.assertEqual(list(external.iterdir()), [marker])
        parent.unlink()
        output = parent / "already-exists"
        output.mkdir(parents=True)
        existing = output / "report.json"
        existing.write_bytes(b"existing review")
        with patch("kicad_tooling.hwrepo.parts_workflow.prepare") as prepare:
            with self.assertRaisesRegex(ValueError, "already exists"):
                mcp_parts.prepare_parts(self.root, "controller", "already-exists", self.summary)
            prepare.assert_not_called()
        self.assertEqual(existing.read_bytes(), b"existing review")

    def test_preferences_creation_and_update_refuse_concurrent_source_changes(self) -> None:
        original_init = parts_workflow.init_preferences
        competing = PurchasingPreferences(boards=8)

        def create_competing(root, project_id, path, preferences):
            write_model(path, competing)
            return original_init(root, project_id, path, preferences)

        with (patch("kicad_tooling.hwrepo.parts_workflow.init_preferences", side_effect=create_competing),
              self.assertRaises(FileExistsError)):
            mcp_parts.save_parts_preferences(self.root, "controller", PurchasingPreferences(boards=2))
        self.assertEqual(read_model(self.preferences, PurchasingPreferences), competing)
        expected = digest(self.preferences)
        original_apply = mcp_files.apply_project_edit
        changed = PurchasingPreferences(boards=9)

        def change_before_apply(*args, **kwargs):
            write_model(self.preferences, changed)
            return original_apply(*args, **kwargs)

        with (patch("kicad_tooling.hwrepo.mcp_files.apply_project_edit", side_effect=change_before_apply),
              self.assertRaisesRegex(ValueError, "hash mismatch")):
            mcp_parts.save_parts_preferences(
                self.root, "controller", PurchasingPreferences(boards=3), expected,
            )
        self.assertEqual(read_model(self.preferences, PurchasingPreferences), changed)
        self.assertFalse(list(self.preferences.parent.glob(".mcp-edit-*")))

    async def test_binary_duplicate_and_wrong_shape_preferences_remain_blocked_receipts(self) -> None:
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            for index, content in enumerate((b"\xff\x00", b'{"boards":2,"boards":3}', b'[]')):
                with self.subTest(content=content):
                    self.preferences.write_bytes(content)
                    result = await client.call_tool("prepare_parts", self.arguments(f"bad-prefs-{index}"))
                    self.assertFalse(result.is_error, result.content)
                    self.assertIsNotNone(result.structured_content)
                    report = result.structured_content
                    self.assertEqual(report["status"], "BLOCKED")
                    self.assertTrue(report["issues"])
                    self.assertFalse(report["purchase_authorized"])
                    self.assertFalse(report["build_authorized"])
                    self.assertFalse((Path(report["receipt_dir"]) / "digikey.csv").exists())
                    self.assertEqual(self.preferences.read_bytes(), content)

    async def test_missing_part_identity_preserves_needs_parts_and_native_failure(self) -> None:
        self.fixture.write_summary(fixture.NETLIST.replace("resistor-1k", "unknown-part"))
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            result = await client.call_tool("prepare_parts", self.arguments())
        self.assertFalse(result.is_error, result.content)
        report = result.structured_content
        self.assertEqual(report["status"], "NEEDS_PARTS")
        self.assertEqual(report["native_status"], "FAIL")
        self.assertEqual(report["evidence"]["review_state"], "UNREVIEWED")
        self.assertFalse(report["build_authorized"])
        self.assertFalse(report["purchase_authorized"])
        self.assertFalse((Path(report["receipt_dir"]) / "digikey.csv").exists())
        self.assertTrue((Path(report["receipt_dir"]) / "bom.csv").is_file())

    async def test_preference_result_roundtrips_and_existing_noop_requires_current_digest(self) -> None:
        async with Client(create_server(self.root, allow_edits=True), mode="legacy") as client:
            arguments = {"project_id": "controller", "preferences": {"boards": 2}}
            created = await client.call_tool("save_parts_preferences", arguments)
            self.assertFalse(created.is_error, created.content)
            report = McpPurchasingPreferencesResult.model_validate_json(json.dumps(created.structured_content))
            self.assertEqual(report.project_id, "controller")
            self.assertEqual(report.preferences.boards, 2)
            self.assertFalse(report.purchase_authorized)
            before = self.preferences.read_bytes()
            noop = await client.call_tool("save_parts_preferences", arguments | {
                "expected_sha256": report.after_sha256,
            })
            self.assertFalse(noop.is_error, noop.content)
            self.assertEqual(self.preferences.read_bytes(), before)
            stale = await client.call_tool("save_parts_preferences", arguments | {
                "expected_sha256": "0" * 64,
            })
            self.assertTrue(stale.is_error)
            self.assertIn("hash mismatch", " ".join(
                item.text for item in stale.content if isinstance(item, TextContent)
            ))
            self.assertEqual(self.preferences.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
