"""MCP source-edit and artifact boundaries, stale writes and bounded text reads."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client
from mcp.types import TextContent

from kicad_tooling.hwrepo import mcp_files
from kicad_tooling.hwrepo.mcp_files import (
    apply_project_edit,
    artifact_path,
    list_artifacts,
    preview_project_edit,
    read_artifact,
    read_project_file,
)
from kicad_tooling.hwrepo.mcp_server import create_server
from tests.support import reference_root


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class McpFilesTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="kicad-mcp-files-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "repository"
        self.root.mkdir()
        shutil.copytree(reference_root() / "catalog", self.root / "catalog")
        self.island = self.root / "examples/projects/controller"
        shutil.copytree(reference_root() / "examples/projects/controller", self.island)
        self.build = self.root / "build"
        self.build.mkdir()
        self.doc = self.island / "docs/mcp-edit.md"
        self.doc.write_text(
            "# Repair note\n\nObserved: old text.\nRepeat repeat.\n", encoding="utf-8"
        )

    def arguments(self, old_text="old text", new_text="reviewed repair"):
        return (self.root, "controller", "docs/mcp-edit.md", digest(self.doc), old_text, new_text)

    def test_artifact_scopes_reject_sources_traversal_and_restore_payload(self) -> None:
        for name in (
            "build/run/log.txt",
            "examples/projects/controller/build/log.txt",
            "examples/products/status-indicator-system/build/report.json",
        ):
            self.assertEqual(artifact_path(self.root, name), self.root / name)
        for name in (
            "README.md",
            "catalog/parts.json",
            "build/../catalog/parts.json",
            "projects/unknown-board/build/log.txt",
            "products/unknown/build/report.json",
            "examples/projects/unknown-board/build/log.txt",
            str(self.doc),
            "projects/board/docs/build/log.txt",
            "build/restores/project/project.json",
            "build/a/restores/data.txt",
            "build/./log.txt",
        ):
            with self.subTest(path=name), self.assertRaises(ValueError):
                artifact_path(self.root, name)

    def test_artifact_linked_parent_and_file_are_rejected(self) -> None:
        outside = self.base / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("outside", encoding="utf-8")
        try:
            (self.build / "linked").symlink_to(outside, target_is_directory=True)
            (self.build / "secret.txt").symlink_to(secret)
        except OSError as exc:
            self.skipTest(str(exc))
        for name in ("build/linked/secret.txt", "build/secret.txt"):
            with self.subTest(path=name), self.assertRaises(ValueError):
                read_artifact(self.root, name)
        with self.assertRaises(ValueError):
            list_artifacts(self.root)

    def test_artifact_listing_is_paginated_one_level_and_hashes_small_files(self) -> None:
        (self.build / "a.json").write_text("{}", encoding="utf-8")
        (self.build / "b").mkdir()
        (self.build / "b/nested.txt").write_text("nested", encoding="utf-8")
        (self.build / "c.csv").write_text("a,b\n", encoding="utf-8")
        (self.build / "restores").mkdir()
        first = list_artifacts(self.root, limit=2)
        self.assertEqual([row.path for row in first.entries], ["build/a.json", "build/b"])
        self.assertEqual(first.entries[0].sha256, digest(self.build / "a.json"))
        self.assertEqual(first.entries[1].kind, "directory")
        self.assertEqual(first.total_entries, 3)
        self.assertTrue(first.truncated)
        second = list_artifacts(self.root, offset=first.next_offset)
        self.assertEqual([row.path for row in second.entries], ["build/c.csv"])
        self.assertFalse(second.truncated)
        self.assertFalse(second.build_authorized)

    def test_utf8_pagination_preserves_codepoints_and_reports_byte_size(self) -> None:
        text = "Aé🙂B\r\nnext"
        (self.build / "unicode.log").write_bytes(text.encode("utf-8"))
        first = read_artifact(self.root, "build/unicode.log", limit=3)
        self.assertEqual(first.text, "Aé🙂")
        self.assertEqual(first.next_offset, 3)
        self.assertEqual(first.total_characters, len(text))
        self.assertEqual(first.size_bytes, len(text.encode("utf-8")))
        second = read_artifact(self.root, "build/unicode.log", offset=3, limit=20)
        self.assertEqual((first.text or "") + (second.text or ""), text)
        self.assertFalse(second.truncated)
        self.assertIsNone(second.next_offset)
        for offset, limit in ((-1, 2), (0, 0), (0, 20_001), (True, 2)):
            with self.subTest(offset=offset, limit=limit), self.assertRaises(ValueError):
                read_artifact(self.root, "build/unicode.log", offset, limit)

    def test_binary_large_and_executable_artifacts_return_metadata_only(self) -> None:
        (self.build / "binary.json").write_bytes(b"\xff\x00")
        binary = read_artifact(self.root, "build/binary.json")
        self.assertEqual(binary.content_kind, "binary")
        self.assertIsNone(binary.text)
        (self.build / "code.py").write_text("print('not exposed')", encoding="utf-8")
        code = read_artifact(self.root, "build/code.py")
        self.assertEqual(code.content_kind, "metadata_only")
        self.assertIsNone(code.text)
        with patch.object(mcp_files, "MAX_TEXT_BYTES", 1):
            large = read_artifact(self.root, "build/binary.json")
        self.assertEqual(large.content_kind, "metadata_only")
        self.assertEqual(large.sha256, digest(self.build / "binary.json"))

    def test_source_read_scope_rejects_code_state_outputs_and_links(self) -> None:
        allowed = read_project_file(self.root, "controller", "docs/mcp-edit.md")
        self.assertEqual(allowed.path, "examples/projects/controller/docs/mcp-edit.md")
        self.assertEqual(allowed.sha256, digest(self.doc))
        for value in (
            "tests/test_board.py",
            "build/output.kicad_sch",
            ".git/config",
            "releases/approval.md",
            "../controller/docs/mcp-edit.md",
            "docs/not-present.md",
            "docs/approval.json",
            "kicad/controller.kicad_prl",
        ):
            with self.subTest(path=value), self.assertRaises(ValueError):
                read_project_file(self.root, "controller", value)
        try:
            (self.island / "docs/linked.md").symlink_to(self.doc)
        except OSError as exc:
            self.skipTest(str(exc))
        with self.assertRaises(ValueError):
            read_project_file(self.root, "controller", "docs/linked.md")

    def test_preview_has_no_writes_and_apply_preserves_mode_and_readback(self) -> None:
        before = self.doc.read_bytes()
        arguments = self.arguments()
        preview = preview_project_edit(*arguments)
        self.assertEqual(self.doc.read_bytes(), before)
        self.assertIn("-Observed: old text.", preview.diff)
        self.assertIn("+Observed: reviewed repair.", preview.diff)
        self.assertEqual(preview.validation, "TEXT_ONLY")
        self.assertTrue(preview.checks_required)
        self.assertFalse(preview.build_authorized)
        mode = self.doc.stat().st_mode
        result = apply_project_edit(*arguments)
        self.assertEqual(result.status, "APPLIED")
        self.assertEqual(result.after_sha256, digest(self.doc))
        self.assertEqual(result.readback_sha256, preview.after_sha256)
        self.assertEqual(self.doc.stat().st_mode, mode)
        self.assertIn("reviewed repair", self.doc.read_text(encoding="utf-8"))
        self.assertFalse(list(self.doc.parent.glob(".mcp-edit-*")))

    def test_stale_digest_and_ambiguous_or_unchanged_replacement_do_not_write(self) -> None:
        arguments = self.arguments()
        self.doc.write_text("A later engineer's change\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            apply_project_edit(*arguments)
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "A later engineer's change\n")
        self.doc.write_text("repeat repeat", encoding="utf-8")
        for old, new in (("repeat", "new"), ("", "new"), ("missing", "new"), ("repeat", "repeat")):
            with self.subTest(old=old, new=new), self.assertRaises(ValueError):
                apply_project_edit(*self.arguments(old, new))
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "repeat repeat")

    def test_overlapping_matches_are_ambiguous(self) -> None:
        self.doc.write_text("aaa", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "exactly once"):
            apply_project_edit(*self.arguments("aa", "b"))
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "aaa")

    @unittest.skipIf(os.name == "nt", "POSIX FIFO")
    def test_special_artifact_files_are_rejected_without_opening(self) -> None:
        os.mkfifo(self.build / "fifo.log")
        with self.assertRaisesRegex(ValueError, "regular file"):
            read_artifact(self.root, "build/fifo.log")

    def test_change_during_prepare_is_not_overwritten_and_temporary_is_removed(self) -> None:
        original_mkstemp = tempfile.mkstemp

        def mutate_source(*args, **kwargs):
            result = original_mkstemp(*args, **kwargs)
            self.doc.write_text("Independent edit during preparation\n", encoding="utf-8")
            return result

        with (
            patch.object(mcp_files.tempfile, "mkstemp", side_effect=mutate_source),
            self.assertRaisesRegex(ValueError, "before publication"),
        ):
            apply_project_edit(*self.arguments())
        self.assertEqual(
            self.doc.read_text(encoding="utf-8"), "Independent edit during preparation\n"
        )
        self.assertFalse(list(self.doc.parent.glob(".mcp-edit-*")))

    def test_json_validation_rejects_id_escape_unknown_toolchain_and_wrong_contract(self) -> None:
        manifest = self.island / "project.json"
        original = manifest.read_bytes()
        for old, new in (
            ('"id": "controller"', '"id": "different"'),
            ('"project": "kicad/controller.kicad_pro"', '"project": "../secret.kicad_pro"'),
            ('"toolchain_id": "kicad-10.0.0"', '"toolchain_id": "nonexistent"'),
            ('"kind": "pcb"', '"kind": "pcb_only"'),
            ('"schema_version": "1"', '"schema_version": "1", "schema_version": "1"'),
        ):
            with self.subTest(replacement=new), self.assertRaises(ValueError):
                apply_project_edit(
                    self.root, "controller", "project.json", digest(manifest), old, new
                )
            self.assertEqual(manifest.read_bytes(), original)
        contract = self.island / "tests/contract.json"
        with self.assertRaises(ValueError):
            preview_project_edit(
                self.root,
                "controller",
                "tests/contract.json",
                digest(contract),
                '"kind": "pcb"',
                '"kind": "pcb_only"',
            )

    def test_manifest_repair_does_not_require_global_discovery(self) -> None:
        manifest = self.island / "project.json"
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(
            text.replace('"schema_version": "1"', '"schema_version": BROKEN'), encoding="utf-8"
        )
        current = read_project_file(self.root, "controller", "project.json")
        result = apply_project_edit(
            self.root,
            "controller",
            "project.json",
            current.sha256,
            '"schema_version": BROKEN',
            '"schema_version": "1"',
        )
        self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["id"], "controller")
        self.assertTrue(result.checks_required)

    def test_valid_contract_change_remains_unapproved(self) -> None:
        contract = self.island / "tests/contract.json"
        preview = preview_project_edit(
            self.root,
            "controller",
            "tests/contract.json",
            digest(contract),
            '"value": "1k"',
            '"value": "1.1k"',
        )
        self.assertEqual(preview.validation, "JSON_MODEL")
        self.assertFalse(preview.build_authorized)
        self.assertTrue(preview.checks_required)

    def test_binary_source_and_oversized_edits_are_rejected(self) -> None:
        self.doc.write_bytes(b"\x00binary")
        with self.assertRaisesRegex(ValueError, "binary NUL"):
            preview_project_edit(*self.arguments("binary", "new"))
        self.doc.write_text("old text", encoding="utf-8")
        with patch.object(mcp_files, "MAX_EDIT_BYTES", 2), self.assertRaises(ValueError):
            apply_project_edit(*self.arguments())
        with self.assertRaises(ValueError):
            preview_project_edit(*self.arguments("old text", "x" * 20_001))

    @unittest.skipIf(os.name == "nt", "POSIX file executable modes")
    def test_executable_mode_blocks_source_edit(self) -> None:
        self.doc.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "non-executable"):
            apply_project_edit(*self.arguments())


class McpFileErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_kicad_json_preserves_actionable_protocol_errors_and_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kicad-mcp-json-errors-") as directory:
            root = Path(directory).resolve()
            shutil.copytree(reference_root() / "catalog", root / "catalog")
            island = root / "examples/projects/controller"
            shutil.copytree(reference_root() / "examples/projects/controller", island)
            source = island / "kicad/review.kicad_pro"
            source.write_text("{}\n", encoding="utf-8")
            original = source.read_bytes()
            async with Client(create_server(root, allow_edits=True), mode="legacy") as client:
                for replacement, expected in (
                    ("[]", "JSON document must be an object"),
                    ("{", "Expecting property name"),
                    ('{"x": 1, "x": 2}', "Duplicate JSON key"),
                    ('{"x": NaN}', "Invalid JSON number"),
                ):
                    for tool in ("preview_project_edit", "apply_project_edit"):
                        with self.subTest(tool=tool, replacement=replacement):
                            result = await client.call_tool(
                                tool,
                                {
                                    "project_id": "controller",
                                    "path": "kicad/review.kicad_pro",
                                    "expected_sha256": digest(source),
                                    "old_text": "{}",
                                    "new_text": replacement,
                                },
                            )
                            self.assertTrue(result.is_error)
                            explanation = "\n".join(
                                item.text
                                for item in result.content
                                if isinstance(item, TextContent)
                            )
                            self.assertIn(expected, explanation)
                            self.assertEqual(source.read_bytes(), original)
            self.assertFalse(list(source.parent.glob(".mcp-edit-*")))


if __name__ == "__main__":
    unittest.main()
