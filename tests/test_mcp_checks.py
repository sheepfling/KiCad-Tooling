"""MCP verification dispatch, authority, and report-boundary checks."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import ProjectVerificationReport
from tests.mcp_test_support import (
    CHECK_TOOLS,
    DEFAULT_TOOLS,
    DOCUMENTS,
    EDIT_TOOLS,
    EXPORT_TOOLS,
    NATIVE_EXPORT_TOOLS,
    WRITE_TOOLS,
    McpTestCase,
    snapshot,
)

pytestmark = [pytest.mark.slow, pytest.mark.template_checkout]


class McpTests(McpTestCase):
    async def test_check_dispatch_preserves_failure_receipt_and_selected_runner(self) -> None:
        failed = ProjectVerificationReport(
            project_id="controller",
            depth="native",
            runner="container",
            status="FAIL",
            run_directory=str(self.root / "build/verification/controller-failed"),
            next_actions=("Repair the failed project test before reviewing this board.",),
        )
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            with patch("kicad_tooling.hwrepo.mcp_server.verify", return_value=failed) as verify:
                data = self.structured(
                    await client.call_tool(
                        "check_project",
                        {
                            "project_id": "controller",
                            "depth": "native",
                            "runner": "container",
                        },
                    )
                )
            self.assertEqual(data, failed.model_dump(mode="json"))
            verify.assert_called_once_with(
                self.root, "controller", depth="native", runner="container"
            )
            with patch("kicad_tooling.hwrepo.mcp_server.verify", return_value=failed) as verify:
                rejected = await client.call_tool(
                    "check_project",
                    {
                        "project_id": "controller",
                        "runner": "arbitrary-command",
                    },
                )
            self.assertTrue(rejected.is_error)
            verify.assert_not_called()

    async def test_portable_check_rejects_native_runners_before_execution(self) -> None:
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            for runner in ("local", "container"):
                for options in ({}, {"depth": "portable"}):
                    with self.subTest(runner=runner, options=options):
                        with patch("kicad_tooling.hwrepo.mcp_server.verify") as verify:
                            rejected = await client.call_tool(
                                "check_project",
                                {
                                    "project_id": "controller",
                                    "runner": runner,
                                    **options,
                                },
                            )
                        self.assertTrue(rejected.is_error, rejected.content)
                        self.assertIn("requires native depth", self.text(rejected))
                        verify.assert_not_called()

    async def test_linked_receipt_directory_is_rejected_before_project_execution(self) -> None:
        external = self.base / "external-receipts"
        external.mkdir()
        for relative in ("build", "build/diagnostics"):
            with self.subTest(relative=relative):
                link = self.root / relative
                link.parent.mkdir(parents=True, exist_ok=True)
                try:
                    link.symlink_to(external, target_is_directory=True)
                except OSError:
                    self.skipTest("Symlink creation unavailable")
                try:
                    async with Client(
                        create_server(self.root, allow_checks=True),
                        mode="legacy",
                    ) as client:
                        with patch("kicad_tooling.hwrepo.mcp_server.verify") as verify:
                            result = await client.call_tool(
                                "check_project",
                                {
                                    "project_id": "controller",
                                },
                            )
                        self.assertTrue(result.is_error, result.content)
                        verify.assert_not_called()
                        self.assertEqual(list(external.iterdir()), [])
                finally:
                    link.unlink()

    async def test_full_surface_annotations_and_disabled_calls_match_authority(self) -> None:
        arguments = {
            "apply_project_edit": {
                "project_id": "controller",
                "path": "README.md",
                "expected_sha256": "0" * 64,
                "old_text": "old",
                "new_text": "new",
            },
            "diagnose_project": {"project_id": "controller"},
            "capture_contract": {"project_id": "controller"},
            "check_scope": {},
            "check_native_scope": {"view_id": "try-one"},
            "export_project": {"project_id": "controller", "export_id": "try-one"},
            "export_3d": {"project_id": "controller", "view_id": "try-one"},
            "prepare_review": {"project_id": "controller", "release_id": "try-one"},
            "prepare_review_scope": {"project_ids": ["controller"], "release_id": "try-one"},
            "package_release": {"manifest": "build/manifest.json", "package_id": "try-one"},
            "restore_package": {"archive": "build/review.zip", "restore_id": "try-one"},
            "generate_views": {"view_id": "try-one"},
            "init_model_map": {"project_id": "controller", "view_id": "try-one"},
            "prepare_parts": {"project_id": "controller", "view_id": "try-one"},
            "save_parts_preferences": {"project_id": "controller", "preferences": {}},
            "apply_model_population": {"project_id": "controller", "plan": "build/plan.json"},
        }
        before = snapshot(self.root)
        async with Client(create_server(self.root), mode="legacy") as client:
            for name, values in arguments.items():
                with self.subTest(tool=name):
                    result = await client.call_tool(name, values)
                    self.assertTrue(result.is_error)
                    self.assertIn("Unknown tool", self.text(result))
        self.assertEqual(snapshot(self.root), before)
        async with Client(
            create_server(
                self.root,
                allow_checks=True,
                allow_writes=True,
                allow_edits=True,
                allow_exports=True,
            ),
            mode="legacy",
        ) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            self.assertEqual(
                set(tools),
                DEFAULT_TOOLS
                | CHECK_TOOLS
                | WRITE_TOOLS
                | EXPORT_TOOLS
                | EDIT_TOOLS
                | NATIVE_EXPORT_TOOLS,
            )
            self.assertEqual(len((await client.list_resources()).resources), len(DOCUMENTS))
            for name in CHECK_TOOLS | NATIVE_EXPORT_TOOLS | EDIT_TOOLS:
                self.assertFalse(tools[name].annotations.read_only_hint, name)
            for name in (
                "read_artifact",
                "preview_project_edit",
                "scan_imports",
                "inspect_contract",
                "inspect_3d_models",
            ):
                self.assertTrue(tools[name].annotations.read_only_hint, name)
            self.assertFalse(tools["diagnose_import"].annotations.read_only_hint)
            self.assertFalse(tools["rescue_project"].annotations.read_only_hint)
            self.assertFalse(tools["preview_model_population"].annotations.read_only_hint)
            self.assertFalse(tools["preview_model_population"].annotations.destructive_hint)

    async def test_scope_and_generated_product_bom_remain_inspectable(self) -> None:
        async with Client(
            create_server(
                self.root,
                allow_checks=True,
                allow_exports=True,
            ),
            mode="legacy",
        ) as client:
            checked = self.structured(
                await client.call_tool(
                    "check_scope",
                    {
                        "project_ids": ["arduino-uno-status-led"],
                    },
                )
            )
            self.assertEqual(checked["status"], "PASS")
            self.assertEqual(checked["report"]["projects"], ["arduino-uno-status-led"])
            generated = self.structured(
                await client.call_tool(
                    "generate_views",
                    {
                        "view_id": "review-views",
                        "product_ids": ["status-indicator-system"],
                    },
                )
            )
            self.assertEqual(generated["status"], "PASS")
            bom = next(path for path in generated["files"] if path.endswith(".bom.csv"))
            result = self.structured(await client.call_tool("read_artifact", {"path": bom}))
            self.assertIn("part_id,revision,quantity", result["text"])
            self.assertIn("training-generic-cable", result["text"])
            self.assertIn("NOT FOR MANUFACTURE", result["text"])
            self.assertFalse(result["build_authorized"])
            duplicate = await client.call_tool("generate_views", {"view_id": "review-views"})
            self.assertTrue(duplicate.is_error)

    async def test_existing_native_report_bom_and_release_paths_cannot_escape(self) -> None:
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            for tool, values in (
                ("diagnose_project", {"project_id": "controller", "bom": "build/bom.csv"}),
                (
                    "diagnose_project",
                    {"project_id": "controller", "native_report": "../summary.json"},
                ),
                ("inspect_contract", {"project_id": "controller", "native_summary": "README.md"}),
                ("check_release", {"manifest": "../../manifest.json"}),
                ("verify_package", {"archive": str(self.project)}),
                ("read_artifact", {"path": "examples/projects/controller/project.json"}),
            ):
                with self.subTest(tool=tool):
                    result = await client.call_tool(tool, values)
                    self.assertTrue(result.is_error, result.content)
            self.assertFalse((self.root / "build").exists())

    async def test_invalid_package_returns_actionable_error_without_executing(self) -> None:
        archive = self.root / "build/broken.zip"
        archive.parent.mkdir()
        archive.write_text("incomplete download", encoding="utf-8")
        async with Client(create_server(self.root), mode="legacy") as client:
            result = await client.call_tool("verify_package", {"archive": "build/broken.zip"})
            self.assertTrue(result.is_error)
            self.assertIn("zip", self.text(result).lower())
            self.assertIn("File is not a zip file", self.text(result))
