"""MCP protocol inventory, project contracts, and documentation access."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from mcp import Client
from pydantic import ValidationError

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    McpProjectReport,
    ProjectManifest,
    ProjectTestContract,
    TemplateInventoryReport,
)
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
                (
                    "new_project",
                    {
                        "project_id": "new-board",
                        "kind": "pcb",
                        "toolchain_id": "kicad-10.0.5",
                    },
                ),
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
            (
                {"allow_checks": True, "allow_exports": True},
                CHECK_TOOLS | EXPORT_TOOLS | NATIVE_EXPORT_TOOLS,
            ),
        ):
            with self.subTest(options=options):
                async with Client(create_server(self.root, **options), mode="legacy") as client:
                    listing = await client.list_tools()
                    self.assertEqual({tool.name for tool in listing.tools}, DEFAULT_TOOLS | enabled)

    async def test_project_report_preserves_manifest_and_independent_contract(self) -> None:
        async with Client(create_server(self.root), mode="legacy") as client:
            data = self.structured(
                await client.call_tool(
                    "get_project",
                    {
                        "project_id": "controller",
                    },
                )
            )
            report = McpProjectReport.model_validate_json(json.dumps(data))
            self.assertEqual(report.schema_version, "1")
            self.assertFalse(report.build_authorized)
            self.assertEqual(report.project.id, "controller")
            self.assertEqual(report.project.toolchain_id, "kicad-10.0.0")
            self.assertEqual(
                McpProjectReport.model_validate_json(report.model_dump_json(by_alias=True)),
                report,
            )
            directory = self.root / "examples/projects/controller"
            self.assertEqual(
                data["manifest"],
                read_model(
                    directory / "project.json",
                    ProjectManifest,
                ).model_dump(mode="json", by_alias=True),
            )
            self.assertEqual(
                data["contract"],
                read_model(
                    directory / "tests/contract.json",
                    ProjectTestContract,
                ).model_dump(mode="json", by_alias=True),
            )
            for identifier in ("missing-board", "../README.md"):
                result = await client.call_tool("get_project", {"project_id": identifier})
                self.assertTrue(result.is_error, identifier)
                self.assertIn("Call list_projects", self.text(result))

    async def test_project_report_rejects_unsupported_version_extra_fields_and_wrong_types(
        self,
    ) -> None:
        async with Client(create_server(self.root), mode="legacy") as client:
            data = self.structured(
                await client.call_tool(
                    "get_project",
                    {
                        "project_id": "controller",
                    },
                )
            )
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
                data = self.structured(
                    await client.call_tool(
                        "doctor",
                        {
                            "project_id": "controller",
                            "native": True,
                        },
                    )
                )
            self.assertEqual(data["status"], "FAIL")
            self.assertFalse(data["build_authorized"])
            self.assertTrue(data["native_requested"])
            self.assertTrue(any(check["status"] == "FAIL" for check in data["checks"]))
        self.assertEqual(snapshot(self.root), before)
