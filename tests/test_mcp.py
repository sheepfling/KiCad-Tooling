"""MCP protocol, checkout boundaries and explicit execution/write capabilities."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client, StdioServerParameters
from mcp.types import CallToolResult, TextContent
from pydantic import ValidationError

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    McpProjectReport,
    ProjectManifest,
    ProjectTestContract,
    ProjectVerificationReport,
    TemplateInventoryReport,
)
from tests import test_visualize
from tests.support import SOURCE_ROOT, initialize_git, reference_root

DEFAULT_TOOLS = {
    "list_projects", "get_project", "doctor", "read_document", "preview_import",
    "scan_imports", "diagnose_import", "rescue_project", "list_artifacts", "read_artifact",
    "read_project_file", "preview_project_edit", "inspect_contract", "check_release", "verify_package",
    "inspect_3d_models", "preview_model_population", "inspect_tool_surfaces",
    "plan_impact", "inspect_sourcing_snapshot",
}
CHECK_TOOLS = {"check_project", "diagnose_project", "capture_contract", "check_scope", "check_native_scope", "analyze_electrical", "check_electrical_scope"}
WRITE_TOOLS = {"new_project", "import_project"}
EXPORT_TOOLS = {"package_release", "restore_package", "generate_views", "prepare_parts", "init_model_map",
                "capture_electrical_inputs", "prepare_part_picker", "preview_part_selection",
                "preview_model_sync", "preview_auto_cad", "prepare_supplier_handoff",
                "export_electrical_charts", "export_electrical_chart_suite", "source_cad",
                "preview_cad_import"}
EDIT_TOOLS = {"apply_project_edit", "apply_model_population", "save_parts_preferences",
              "init_electrical", "apply_part_selection", "apply_auto_cad",
              "apply_cad_import"}
NATIVE_EXPORT_TOOLS = {"export_project", "prepare_review", "prepare_review_scope", "export_3d", "convert_pcb", "check_step_alignment"}
DOCUMENTS = {
    "start-here": "START_HERE.md",
    "first-board": "FIRST_BOARD.md",
    "diagnostics": "DIAGNOSTICS.md",
    "import-workflow": "IMPORT_WORKFLOW.md",
    "contributor-guide": "CONTRIBUTOR_GUIDE.md",
    "checks-and-ci": "CHECKS_AND_CI.md",
    "mcp": "MCP.md",
    "bom-policy": "BOM_POLICY.md",
    "release-readiness": "RELEASE_READINESS.md",
    "release-storage": "RELEASE_STORAGE.md",
    "project-kinds": "PROJECT_KINDS.md",
    "libraries": "LIBRARIES.md",
    "authority-model": "AUTHORITY_MODEL.md",
    "assurance-profiles": "ASSURANCE_PROFILES.md",
    "three-d-workflow": "THREE_D_WORKFLOW.md",
    "parts-to-order": "PARTS_TO_ORDER.md",
    "tool-surfaces": "TOOL_SURFACES.md",
    "electrical-analysis": "ELECTRICAL_ANALYSIS.md",
    "cad-sourcing": "CAD_SOURCING.md",
}


def snapshot(root: Path) -> dict[str, str]:
    """Capture authored files and directory creation, excluding mutable Git state."""
    result: dict[str, str] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".git" in relative.parts or "__pycache__" in relative.parts:
            continue
        if path.is_symlink():
            result[relative.as_posix()] = f"link:{path.readlink()}"
        elif path.is_file():
            result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            result[relative.as_posix()] = "directory"
    return result


class McpTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="kicad-mcp-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "repository"
        shutil.copytree(
            reference_root(), self.root,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        initialize_git(self.root)
        self.source = self.base / "Incoming board"
        self.source.mkdir()
        self.project = self.source / "Incoming board.kicad_pro"
        self.project.write_text("{}", encoding="utf-8")
        self.project.with_suffix(".kicad_sch").write_text("(kicad_sch)", encoding="utf-8")
        self.project.with_suffix(".kicad_pcb").write_text("(kicad_pcb)", encoding="utf-8")

    def structured(self, result: CallToolResult):
        self.assertFalse(result.is_error, result.content)
        self.assertIsNotNone(result.structured_content)
        return result.structured_content

    @staticmethod
    def text(result: CallToolResult) -> str:
        return "\n".join(item.text for item in result.content if isinstance(item, TextContent))

    def import_arguments(self, source: Path | None = None) -> dict[str, str]:
        return {
            "source": str(source or self.project),
            "project_id": "incoming-board",
            "toolchain_id": "kicad-10.0.5",
        }

    async def test_handshake_discovery_and_structured_inventory(self) -> None:
        before = snapshot(self.root)
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertIsNotNone(client.server_info)
            self.assertTrue(client.protocol_version)
            listing = await client.list_tools()
            self.assertEqual({tool.name for tool in listing.tools}, DEFAULT_TOOLS)
            inventory_tool = next(tool for tool in listing.tools if tool.name == "list_projects")
            self.assertIsNotNone(inventory_tool.output_schema)
            data = self.structured(await client.call_tool("list_projects"))
            report = TemplateInventoryReport.model_validate_json(json.dumps(data))
            self.assertEqual(report.status, "PASS")
            self.assertFalse(report.build_authorized)
            controller = next(project for project in report.projects if project.id == "controller")
            self.assertEqual(controller.toolchain_id, "kicad-10.0.0")
            self.assertEqual(controller.readiness, "INPUTS_PRESENT")
            self.assertIn("kicad-10.0.5", {toolchain.id for toolchain in report.toolchains})
        self.assertEqual(snapshot(self.root), before)

    async def test_unregistered_execution_and_write_tools_cannot_be_called(self) -> None:
        before = snapshot(self.root)
        async with Client(create_server(self.root), mode="legacy") as client:
            for name, arguments in (
                ("check_project", {"project_id": "controller"}),
                ("new_project", {
                    "project_id": "new-board", "kind": "pcb", "toolchain_id": "kicad-10.0.5",
                }),
                ("import_project", self.import_arguments()),
            ):
                with self.subTest(tool=name):
                    result = await client.call_tool(name, arguments)
                    self.assertTrue(result.is_error)
                    self.assertIn("Unknown tool", self.text(result))
        self.assertEqual(snapshot(self.root), before)

    async def test_write_and_execution_capabilities_are_independent(self) -> None:
        for options, enabled in (
            ({"allow_checks": True}, CHECK_TOOLS),
            ({"allow_writes": True}, WRITE_TOOLS),
            ({"allow_downloads": True}, set()),
            ({"allow_supplier_submissions": True}, {"submit_supplier_handoff"}),
            ({"allow_edits": True}, EDIT_TOOLS),
            ({"allow_exports": True}, EXPORT_TOOLS),
            ({"allow_checks": True, "allow_exports": True},
             CHECK_TOOLS | EXPORT_TOOLS | NATIVE_EXPORT_TOOLS),
        ):
            with self.subTest(options=options):
                async with Client(create_server(self.root, **options), mode="legacy") as client:
                    listing = await client.list_tools()
                    self.assertEqual({tool.name for tool in listing.tools}, DEFAULT_TOOLS | enabled)

    async def test_project_report_preserves_manifest_and_independent_contract(self) -> None:
        async with Client(create_server(self.root), mode="legacy") as client:
            data = self.structured(await client.call_tool("get_project", {
                "project_id": "controller",
            }))
            report = McpProjectReport.model_validate_json(json.dumps(data))
            self.assertEqual(report.schema_version, "1")
            self.assertFalse(report.build_authorized)
            self.assertEqual(report.project.id, "controller")
            self.assertEqual(report.project.toolchain_id, "kicad-10.0.0")
            self.assertEqual(
                McpProjectReport.model_validate_json(report.model_dump_json(by_alias=True)), report,
            )
            directory = self.root / "examples/projects/controller"
            self.assertEqual(data["manifest"], read_model(
                directory / "project.json", ProjectManifest,
            ).model_dump(mode="json", by_alias=True))
            self.assertEqual(data["contract"], read_model(
                directory / "tests/contract.json", ProjectTestContract,
            ).model_dump(mode="json", by_alias=True))
            for identifier in ("missing-board", "../README.md"):
                result = await client.call_tool("get_project", {"project_id": identifier})
                self.assertTrue(result.is_error, identifier)
                self.assertIn("Call list_projects", self.text(result))

    async def test_project_report_rejects_unsupported_version_extra_fields_and_wrong_types(self) -> None:
        async with Client(create_server(self.root), mode="legacy") as client:
            data = self.structured(await client.call_tool("get_project", {
                "project_id": "controller",
            }))
        for update, field in (
            ({"schema_version": "2"}, "schema_version"),
            ({"schema_version": 1}, "schema_version"),
            ({"unexpected": "not part of the contract"}, "unexpected"),
            ({"build_authorized": "false"}, "build_authorized"),
            ({"project": data["project"] | {"id": 123}}, "project.id"),
        ):
            with self.subTest(update=update):
                with self.assertRaises(ValidationError) as rejected:
                    McpProjectReport.model_validate_json(json.dumps(data | update))
                self.assertIn(field, str(rejected.exception))

    async def test_each_document_is_available_as_tool_and_resource(self) -> None:
        async with Client(create_server(self.root), mode="legacy") as client:
            resources = await client.list_resources()
            self.assertEqual(
                {str(resource.uri) for resource in resources.resources},
                {f"kicad://docs/{name}" for name in DOCUMENTS},
            )
            for name, filename in DOCUMENTS.items():
                with self.subTest(document=name):
                    expected = (self.root / "docs/workflow" / filename).read_text(encoding="utf-8")
                    result = await client.call_tool("read_document", {"name": name})
                    self.assertFalse(result.is_error, result.content)
                    self.assertEqual(self.text(result), expected)
                    resource = await client.read_resource(f"kicad://docs/{name}")
                    self.assertEqual(len(resource.contents), 1)
                    self.assertEqual(resource.contents[0].text, expected)
            denied = await client.call_tool("read_document", {"name": "../../README.md"})
            self.assertTrue(denied.is_error)

    async def test_doctor_returns_readiness_without_creating_check_receipts(self) -> None:
        before = snapshot(self.root)
        async with Client(create_server(self.root), mode="legacy") as client:
            # Native tools may be absent on a contributor's machine; that is an
            # environment finding, never an MCP success substituted for readiness.
            with patch("kicad_tooling.hwrepo.doctor.shutil.which", return_value=None):
                data = self.structured(await client.call_tool("doctor", {
                    "project_id": "controller", "native": True,
                }))
            self.assertEqual(data["status"], "FAIL")
            self.assertFalse(data["build_authorized"])
            self.assertTrue(data["native_requested"])
            self.assertTrue(any(check["status"] == "FAIL" for check in data["checks"]))
        self.assertEqual(snapshot(self.root), before)

    async def test_external_preview_requires_startup_root_and_preserves_source_and_checkout(self) -> None:
        before_root, before_source = snapshot(self.root), snapshot(self.source)
        async with Client(create_server(self.root), mode="legacy") as client:
            denied = await client.call_tool("preview_import", self.import_arguments())
            self.assertTrue(denied.is_error, denied.content)
            self.assertIn("--import-root", self.text(denied))
        async with Client(
            create_server(self.root, import_roots=(self.source,)), mode="legacy",
        ) as client:
            data = self.structured(await client.call_tool("preview_import", self.import_arguments()))
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
            data = self.structured(await client.call_tool(
                "preview_import", self.import_arguments(Path("incoming") / self.project.name),
            ))
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
        async with Client(create_server(
            self.root, allow_writes=True, import_roots=(self.source,),
        ), mode="legacy") as client:
            data = self.structured(await client.call_tool("import_project", self.import_arguments()))
            self.assertEqual(data["status"], "PASS", data["issues"])
            self.assertFalse(data["dry_run"])
            self.assertTrue(data["review_required"])
            island = self.root / data["directory"]
            for name in before_source:
                self.assertEqual((island / "kicad" / name).read_bytes(), (self.source / name).read_bytes())
            listed = self.structured(await client.call_tool("list_projects"))
            self.assertIn("incoming-board", {project["id"] for project in listed["projects"]})
        self.assertEqual(snapshot(self.source), before_source)

    async def test_check_dispatch_preserves_failure_receipt_and_selected_runner(self) -> None:
        failed = ProjectVerificationReport(
            project_id="controller", depth="native", runner="container", status="FAIL",
            run_directory=str(self.root / "build/verification/controller-failed"),
            next_actions=("Repair the failed project test before reviewing this board.",),
        )
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            with patch("kicad_tooling.hwrepo.mcp_server.verify", return_value=failed) as verify:
                data = self.structured(await client.call_tool("check_project", {
                    "project_id": "controller", "depth": "native", "runner": "container",
                }))
            self.assertEqual(data, failed.model_dump(mode="json"))
            verify.assert_called_once_with(self.root, "controller", depth="native", runner="container")
            with patch("kicad_tooling.hwrepo.mcp_server.verify", return_value=failed) as verify:
                rejected = await client.call_tool("check_project", {
                    "project_id": "controller", "runner": "arbitrary-command",
                })
            self.assertTrue(rejected.is_error)
            verify.assert_not_called()

    async def test_portable_check_rejects_native_runners_before_execution(self) -> None:
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            for runner in ("local", "container"):
                for options in ({}, {"depth": "portable"}):
                    with self.subTest(runner=runner, options=options):
                        with patch("kicad_tooling.hwrepo.mcp_server.verify") as verify:
                            rejected = await client.call_tool("check_project", {
                                "project_id": "controller", "runner": runner, **options,
                            })
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
                        create_server(self.root, allow_checks=True), mode="legacy",
                    ) as client:
                        with patch("kicad_tooling.hwrepo.mcp_server.verify") as verify:
                            result = await client.call_tool("check_project", {
                                "project_id": "controller",
                            })
                        self.assertTrue(result.is_error, result.content)
                        verify.assert_not_called()
                        self.assertEqual(list(external.iterdir()), [])
                finally:
                    link.unlink()

    async def test_full_surface_annotations_and_disabled_calls_match_authority(self) -> None:
        arguments = {
            "apply_project_edit": {"project_id": "controller", "path": "README.md",
                "expected_sha256": "0" * 64, "old_text": "old", "new_text": "new"},
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
        async with Client(create_server(
            self.root, allow_checks=True, allow_writes=True, allow_edits=True, allow_exports=True,
        ), mode="legacy") as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            self.assertEqual(set(tools), DEFAULT_TOOLS | CHECK_TOOLS | WRITE_TOOLS
                             | EXPORT_TOOLS | EDIT_TOOLS | NATIVE_EXPORT_TOOLS)
            self.assertEqual(len((await client.list_resources()).resources), len(DOCUMENTS))
            for name in CHECK_TOOLS | NATIVE_EXPORT_TOOLS | EDIT_TOOLS:
                self.assertFalse(tools[name].annotations.read_only_hint, name)
            for name in ("read_artifact", "preview_project_edit", "scan_imports", "inspect_contract", "inspect_3d_models"):
                self.assertTrue(tools[name].annotations.read_only_hint, name)
            self.assertFalse(tools["diagnose_import"].annotations.read_only_hint)
            self.assertFalse(tools["rescue_project"].annotations.read_only_hint)
            self.assertFalse(tools["preview_model_population"].annotations.read_only_hint)
            self.assertFalse(tools["preview_model_population"].annotations.destructive_hint)

    async def test_import_triage_receipt_source_edit_and_recheck_sequence(self) -> None:
        async with Client(create_server(
            self.root, import_roots=(self.source,), allow_writes=True,
            allow_edits=True, allow_checks=True,
        ), mode="legacy") as client:
            scanned = self.structured(await client.call_tool("scan_imports", {
                "source_directory": str(self.source), "toolchain_id": "kicad-10.0.5",
            }))
            self.assertEqual(len(scanned["candidates"]), 1)
            triage = self.structured(await client.call_tool("diagnose_import", self.import_arguments()))
            self.assertEqual(triage["status"], "PASS")
            receipt = Path(triage["run_directory"]).relative_to(self.root).as_posix()
            listing = self.structured(await client.call_tool("list_artifacts", {"directory": receipt}))
            self.assertIn(receipt + "/diagnosis.json", {item["path"] for item in listing["entries"]})
            artifact = self.structured(await client.call_tool("read_artifact", {
                "path": receipt + "/diagnosis.json",
            }))
            self.assertEqual(json.loads(artifact["text"])["project_id"], "incoming-board")
            imported = self.structured(await client.call_tool("import_project", self.import_arguments()))
            self.assertEqual(imported["status"], "PASS")
            source = self.structured(await client.call_tool("read_project_file", {
                "project_id": "incoming-board", "path": "docs/README.md",
            }))
            old = source["text"].splitlines()[0]
            edit = {"project_id": "incoming-board", "path": "docs/README.md",
                    "expected_sha256": source["sha256"], "old_text": old,
                    "new_text": old + " (review in progress)"}
            preview = self.structured(await client.call_tool("preview_project_edit", edit))
            self.assertIn("review in progress", preview["diff"])
            self.assertEqual(source["sha256"], preview["before_sha256"])
            applied = self.structured(await client.call_tool("apply_project_edit", edit))
            self.assertEqual(applied["after_sha256"], preview["after_sha256"])
            self.assertEqual(applied["readback_sha256"], preview["after_sha256"])
            self.assertTrue(applied["checks_required"])
            stale = await client.call_tool("apply_project_edit", edit)
            self.assertTrue(stale.is_error)
            diagnosis = self.structured(await client.call_tool("diagnose_project", {
                "project_id": "incoming-board",
            }))
            self.assertEqual(diagnosis["status"], "NEEDS_WORK")
            self.assertTrue(any(row["severity"] == "BLOCKING" for row in diagnosis["findings"]))
            checked = self.structured(await client.call_tool("check_project", {
                "project_id": "incoming-board",
            }))
            # Portable structure can pass while diagnosis still requires electrical review.
            self.assertEqual(checked["status"], "PASS")
            self.assertFalse(checked["build_authorized"])
            # Importing and editing notes never fabricates the independent circuit contract.
            project = self.structured(await client.call_tool("get_project", {
                "project_id": "incoming-board",
            }))
            self.assertEqual(project["contract"]["validation"]["components"], {})
            self.assertEqual(project["contract"]["validation"]["nets"], {})

    async def test_scope_and_generated_product_bom_remain_inspectable(self) -> None:
        async with Client(create_server(
            self.root, allow_checks=True, allow_exports=True,
        ), mode="legacy") as client:
            checked = self.structured(await client.call_tool("check_scope", {
                "project_ids": ["arduino-uno-status-led"],
            }))
            self.assertEqual(checked["status"], "PASS")
            self.assertEqual(checked["report"]["projects"], ["arduino-uno-status-led"])
            generated = self.structured(await client.call_tool("generate_views", {
                "view_id": "review-views", "product_ids": ["status-indicator-system"],
            }))
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
                ("diagnose_project", {"project_id": "controller", "native_report": "../summary.json"}),
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

    async def test_3d_inventory_is_read_only_and_preserves_model_review(self) -> None:
        before = snapshot(self.root)
        async with Client(create_server(self.root), mode="legacy") as client:
            data = self.structured(await client.call_tool("inspect_3d_models", {
                "project_id": "arduino-uno-status-led",
            }))
            self.assertEqual(data["status"], "REVIEW")
            self.assertFalse(data["build_authorized"])
            self.assertTrue(data["footprints"])
            for project in ("../outside", "passive-signal-reference", "missing-project"):
                rejected = await client.call_tool("inspect_3d_models", {"project_id": project})
                self.assertTrue(rejected.is_error, rejected.content)
        self.assertEqual(snapshot(self.root), before)

    async def test_3d_export_handoff_keeps_review_and_rejects_unsafe_or_used_output(self) -> None:
        payloads = {"top.png": test_visualize.PNG, "angled.png": test_visualize.PNG,
                    "board.step": test_visualize.STEP, "board.glb": test_visualize.GLB}

        def native(_root, output, _config, selected, cli, args, timeout=300):
            self.assertEqual(selected, "local")
            self.assertEqual(cli, "kicad-cli")
            if args == ("version",):
                return test_visualize.evidence(args, stdout="10.0.5\n")
            filename = Path(args[args.index("-o") + 1]).name
            (output / filename).write_bytes(payloads[filename])
            return test_visualize.evidence(args)

        options = {"project_id": "arduino-uno-status-led", "view_id": "review-one", "runner": "local"}
        async with Client(create_server(
            self.root, allow_checks=True, allow_exports=True,
        ), mode="legacy") as client:
            tool = next(item for item in (await client.list_tools()).tools if item.name == "export_3d")
            self.assertFalse(tool.annotations.read_only_hint)
            self.assertEqual(set(tool.input_schema["properties"]), {"project_id", "view_id", "runner", "assembly_variant"})
            with (patch("kicad_tooling.hwrepo.three_d.doctor", return_value=test_visualize.passing_doctor()),
                  patch("kicad_tooling.hwrepo.three_d._run_kicad", side_effect=native)):
                report = self.structured(await client.call_tool("export_3d", options))
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["models"]["status"], "REVIEW")
            self.assertFalse(report["build_authorized"])
            self.assertEqual(report["run_directory"], str(self.root / "build/3d/review-one"))
            self.assertEqual(set(report["artifacts_sha256"]), set(payloads))
            saved = self.structured(await client.call_tool("read_artifact", {
                "path": "build/3d/review-one/visualization.json",
            }))
            self.assertEqual(json.loads(saved["text"])["models"]["status"], "REVIEW")
            with patch("kicad_tooling.hwrepo.three_d.generate") as generate:
                for update in ({}, {"view_id": "../escape"}, {"view_id": "/tmp/escape"},
                               {"view_id": "invalid-runner", "runner": "arbitrary-command"}):
                    rejected = await client.call_tool("export_3d", options | update)
                    self.assertTrue(rejected.is_error, rejected.content)
                generate.assert_not_called()

    def population_arguments(self):
        project_id = "arduino-uno-status-led"
        island = self.root / f"examples/projects/{project_id}"
        board = island / f"kicad/{project_id}.kicad_pcb"
        model = island / "kicad/models/Header_1x02.step"
        model.parent.mkdir(parents=True, exist_ok=True)
        model.write_bytes(test_visualize.STEP)
        return {
            "project_id": project_id,
            "board_sha256": hashlib.sha256(board.read_bytes()).hexdigest(),
            "assignments": [{"reference": "J1", "model": model.relative_to(self.root).as_posix()}],
        }

    async def test_model_population_preview_and_reviewed_apply_preserve_source_scope(self) -> None:
        arguments = self.population_arguments()
        before = snapshot(self.root)
        async with Client(create_server(self.root), mode="legacy") as client:
            plan = self.structured(await client.call_tool("preview_model_population", arguments))
            self.assertEqual(plan["status"], "PLAN", plan["error"])
            self.assertFalse(plan["build_authorized"])
            self.assertTrue(plan["checks_required"])
            self.assertIn("${KIPRJMOD}/models/Header_1x02.step", plan["board_diff"])
            self.assertIn("kicad/models/Header_1x02.step", plan["manifest_diff"])
            self.assertEqual({key: value for key, value in snapshot(self.root).items()
                              if Path(key).parts[0] != "build"}, before)
            receipt = Path(plan["run_directory"]).relative_to(self.root)
            saved = self.structured(await client.call_tool("read_artifact", {
                "path": (receipt / "locked-model-map.json").as_posix(),
            }))
            saved_map = json.loads(saved["text"])
            self.assertEqual(saved_map["manifest_sha256"], plan["manifest_sha256"])
            self.assertEqual(saved_map["assignments"][0]["reference"], "J1")
            self.assertEqual(saved_map["assignments"][0]["model"], arguments["assignments"][0]["model"])
            apply_arguments = {"project_id": arguments["project_id"],
                               "plan": (receipt / "model-population.json").as_posix()}
            self.assertTrue((await client.call_tool("apply_model_population", apply_arguments)).is_error)
        async with Client(create_server(self.root, allow_edits=True), mode="legacy") as client:
            applied = self.structured(await client.call_tool("apply_model_population", apply_arguments))
            self.assertEqual(applied["status"], "APPLIED", applied["error"])
            self.assertFalse(applied["build_authorized"])
            self.assertTrue(applied["checks_required"])
            self.assertEqual(applied["board_diff"], plan["board_diff"])
            self.assertNotEqual(applied["run_directory"], plan["run_directory"])
            board = self.structured(await client.call_tool("read_project_file", {
                "project_id": arguments["project_id"],
                "path": f"kicad/{arguments['project_id']}.kicad_pcb",
            }))
            self.assertIn('${KIPRJMOD}/models/Header_1x02.step', board["text"])
            repeated = self.structured(await client.call_tool("apply_model_population", apply_arguments))
            self.assertEqual(repeated["status"], "FAIL")
        after = {key: value for key, value in snapshot(self.root).items() if Path(key).parts[0] != "build"}
        changed = {key for key in before | after if before.get(key) != after.get(key)}
        self.assertEqual(changed, {plan["board"], plan["manifest"]})

    async def test_model_population_apply_rejects_stale_source_assets_and_map(self) -> None:
        arguments = self.population_arguments()
        board = self.root / f"examples/projects/{arguments['project_id']}/kicad/{arguments['project_id']}.kicad_pcb"
        manifest = board.parent.parent / "project.json"
        model = self.root / arguments["assignments"][0]["model"]
        originals = {path: path.read_bytes() for path in (board, manifest, model)}
        async with Client(create_server(self.root, allow_edits=True), mode="legacy") as client:
            for changed in ("board", "manifest", "model", "map"):
                with self.subTest(changed=changed):
                    for path, contents in originals.items():
                        path.write_bytes(contents)
                    plan = self.structured(await client.call_tool("preview_model_population", arguments))
                    self.assertEqual(plan["status"], "PLAN", plan["error"])
                    receipt = Path(plan["run_directory"])
                    path = {"board": board, "manifest": manifest, "model": model,
                            "map": receipt / "locked-model-map.json"}[changed]
                    if changed == "map":
                        data = json.loads(path.read_text())
                        data["assignments"][0]["reference"] = "J2"
                        path.write_text(json.dumps(data))
                    else:
                        path.write_bytes(path.read_bytes() + b"\n")
                    before = (board.read_bytes(), manifest.read_bytes())
                    rejected = self.structured(await client.call_tool("apply_model_population", {
                        "project_id": arguments["project_id"],
                        "plan": (receipt / "model-population.json").relative_to(self.root).as_posix(),
                    }))
                    self.assertEqual(rejected["status"], "FAIL", rejected["error"])
                    self.assertEqual((board.read_bytes(), manifest.read_bytes()), before)

    async def test_model_population_rejects_unsafe_plan_and_map_before_source_edit(self) -> None:
        arguments = self.population_arguments()
        async with Client(create_server(self.root, allow_edits=True), mode="legacy") as client:
            plan = self.structured(await client.call_tool("preview_model_population", arguments))
            receipt = Path(plan["run_directory"])
            name = (receipt / "model-population.json").relative_to(self.root).as_posix()
            before = snapshot(self.root)
            for path in ("../outside.json", str(receipt / "model-population.json"),
                         "examples/projects/controller/project.json"):
                with self.subTest(path=path):
                    result = await client.call_tool("apply_model_population", {
                        "project_id": arguments["project_id"], "plan": path,
                    })
                    self.assertTrue(result.is_error, result.content)
            mismatch = await client.call_tool("apply_model_population", {
                "project_id": "controller", "plan": name,
            })
            self.assertTrue(mismatch.is_error, mismatch.content)
            self.assertEqual(snapshot(self.root), before)
            spec = receipt / "locked-model-map.json"
            outside = self.base / "model-map.json"
            spec.replace(outside)
            spec.symlink_to(outside)
            with patch("kicad_tooling.hwrepo.mcp_workflow.model_population.populate_models") as populate:
                result = await client.call_tool("apply_model_population", {
                    "project_id": arguments["project_id"], "plan": name,
                })
                self.assertTrue(result.is_error, result.content)
                populate.assert_not_called()

    async def test_stdio_cli_uses_explicit_checkout_from_unrelated_working_directory(self) -> None:
        caller = self.base / "caller"
        caller.mkdir()
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-B", "-m", "kicad_tooling.mcp", "--root", str(self.root)],
            cwd=caller,
            env={"PYTHONPATH": str(SOURCE_ROOT), "PYTHONDONTWRITEBYTECODE": "1"},
        )
        async with Client(parameters, mode="legacy", read_timeout_seconds=20) as client:
            self.assertIsNotNone(client.server_info)
            data = self.structured(await client.call_tool("list_projects"))
            self.assertIn("controller", {project["id"] for project in data["projects"]})
            listing = await client.list_tools()
            self.assertEqual({tool.name for tool in listing.tools}, DEFAULT_TOOLS)
        self.assertEqual(list(caller.iterdir()), [])

    def test_cli_refuses_implicit_or_relative_checkout_selection(self) -> None:
        environment = os.environ | {"PYTHONPATH": str(SOURCE_ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
        for arguments in ((), ("--root", "repository")):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    (sys.executable, "-B", "-m", "kicad_tooling.mcp", *arguments),
                    cwd=self.base, env=environment, capture_output=True, text=True,
                    input="", timeout=20, check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("root", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
