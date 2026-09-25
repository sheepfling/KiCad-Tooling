"""MCP purchasing capabilities, source-bound receipts and reviewed preference edits."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client
from mcp.types import CallToolResult, TextContent

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    ComponentIdentity,
    PartRecord,
    PartsCatalog,
    PartStatus,
    ProjectKind,
    ProjectManifest,
    PurchasingPreferences,
    PurchasingReport,
    ValidationSummary,
)
from kicad_tooling.validate import hashes
from tests import test_parts_workflow as parts_fixture
from tests.support import reference_root


class McpPartsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="mcp-parts-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "repository"
        shutil.copytree(reference_root(), self.root,
                        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"))
        self.project_id = "controller"
        self.island = self.root / "examples/projects/controller"
        self.manifest_path = self.island / "project.json"
        manifest = read_model(self.manifest_path, ProjectManifest)
        write_model(self.manifest_path, manifest.model_copy(update={
            "component_identity": ComponentIdentity(required=True, part_ids=("resistor-1k",)),
        }))
        write_model(self.root / "catalog/parts.json", PartsCatalog(schema_version="0.1", parts=(PartRecord(
            id="resistor-1k", revision="A", description="Protocol-test identity only",
            part_class="resistor", unit="each", manufacturer="Vishay",
            mpn="MRS25000C1001FCT00", datasheet_url="https://example.invalid/test-only",
            lifecycle="active", status=PartStatus.APPROVED,
        ),)))
        self.config = load_config(self.root, self.manifest_path)
        self.native = self.root / "build/native/controller"
        self.native.mkdir(parents=True)
        self.preferences_path = self.island / "docs/purchasing.json"
        self.write_summary()

    def write_summary(self) -> None:
        (self.native / "netlist.xml").write_text(parts_fixture.NETLIST, encoding="utf-8")
        write_model(self.native / "netlist.command.json", parts_fixture.command())
        current = hashes(self.root, self.config.source_roots)
        self.summary = ValidationSummary(
            timestamp_utc="2026-09-24T00:00:00+00:00", checked_commit="LOCAL_UNBOUND",
            project_id=self.project_id, project_kind=ProjectKind.PCB,
            checks={
                "source_scope": CheckEvidence(status="PASS", source_hashes=current),
                "source_unchanged": CheckEvidence(status="PASS", source_hashes=current),
                "toolchain": CheckEvidence(status="PASS", observed_version=self.config.kicad_version,
                                           image=self.config.image),
                "netlist": CheckEvidence(status="FAIL", returncode=0,
                                         error="Independent electrical contract differs"),
            },
            status="FAIL", artifacts_sha256={
                "netlist.xml": digest(self.native / "netlist.xml"),
                "netlist.command.json": digest(self.native / "netlist.command.json"),
            },
        )
        write_model(self.native / "summary.json", self.summary)

    def arguments(self, view_id: str = "order-review"):
        return {"project_id": self.project_id, "view_id": view_id,
                "native_summary": "build/native/controller/summary.json"}

    def structured(self, result: CallToolResult):
        self.assertFalse(result.is_error, self.text(result))
        self.assertIsNotNone(result.structured_content)
        return result.structured_content

    @staticmethod
    def text(result: CallToolResult) -> str:
        return "\n".join(item.text for item in result.content if isinstance(item, TextContent))

    def source_snapshot(self) -> dict[str, str]:
        return {path.relative_to(self.root).as_posix(): digest(path)
                for path in self.root.rglob("*") if path.is_file()
                and path.relative_to(self.root).parts[0] != "build"}

    async def test_parts_and_preferences_have_independent_startup_capabilities(self) -> None:
        before = self.source_snapshot()
        for options, prepare_enabled, save_enabled in (
            ({}, False, False), ({"allow_checks": True}, False, False),
            ({"allow_edits": True}, False, True), ({"allow_exports": True}, True, False),
        ):
            with self.subTest(options=options):
                async with Client(create_server(self.root, **options), mode="legacy") as client:
                    tools = {tool.name: tool for tool in (await client.list_tools()).tools}
                    self.assertEqual("prepare_parts" in tools, prepare_enabled)
                    self.assertEqual("save_parts_preferences" in tools, save_enabled)
                    if not prepare_enabled:
                        result = await client.call_tool("prepare_parts", self.arguments())
                        self.assertTrue(result.is_error)
                    else:
                        self.assertNotIn("cli", tools["prepare_parts"].input_schema["properties"])
                        self.assertNotIn("output", tools["prepare_parts"].input_schema["properties"])
                        result = await client.call_tool("prepare_parts", {
                            "project_id": self.project_id, "view_id": "cannot-capture",
                        })
                        self.assertTrue(result.is_error, result.content)
                        self.assertFalse((self.root / "build/parts/cannot-capture").exists())
                    if not save_enabled:
                        result = await client.call_tool("save_parts_preferences", {
                            "project_id": self.project_id, "preferences": {"boards": 3},
                        })
                        self.assertTrue(result.is_error)
        self.assertEqual(self.source_snapshot(), before)

    async def test_saved_evidence_prepares_quantities_and_retains_native_failure(self) -> None:
        before = self.source_snapshot()
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            with patch("kicad_tooling.hwrepo.contract_coach.run_command", side_effect=AssertionError("native execution")):
                data = self.structured(await client.call_tool("prepare_parts", self.arguments() | {
                    "boards": 10, "spare_percent": 10, "spare_minimum": 3,
                }))
            report = PurchasingReport.model_validate_json(json.dumps(data))
            self.assertEqual(report.status, "READY_FOR_ORDER_REVIEW", report.issues)
            self.assertEqual(report.native_status, "FAIL")
            self.assertFalse(report.purchase_authorized)
            self.assertFalse(report.build_authorized)
            self.assertIsNotNone(report.plan)
            assert report.plan is not None
            self.assertEqual(report.plan.lines[0].quantity, 23)
            self.assertEqual(report.plan.excluded_references, ("C1",))
            receipt = self.root / "build/parts/order-review"
            self.assertEqual(Path(report.receipt_dir), receipt)
            self.assertEqual(read_model(receipt / "report.json", PurchasingReport), report)
            self.assertTrue((receipt / "index.html").is_file())
            saved = self.structured(await client.call_tool("read_artifact", {
                "path": "build/parts/order-review/digikey.csv",
            }))
            self.assertIn("23", saved["text"])
            reused = await client.call_tool("prepare_parts", self.arguments())
            self.assertTrue(reused.is_error)
        self.assertEqual(self.source_snapshot(), before)

    async def test_stale_wrong_project_and_tampered_evidence_return_blocked_receipts(self) -> None:
        source = self.island / "kicad/controller.kicad_sch"
        original = source.read_bytes()
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            for mutation in ("source", "project", "netlist"):
                with self.subTest(mutation=mutation):
                    source.write_bytes(original)
                    self.write_summary()
                    if mutation == "source":
                        source.write_bytes(original + b"\n")
                    elif mutation == "project":
                        write_model(self.native / "summary.json", self.summary.model_copy(
                            update={"project_id": "passive-signal-reference"}))
                    else:
                        (self.native / "netlist.xml").write_text(parts_fixture.NETLIST + "\n")
                    report = self.structured(await client.call_tool("prepare_parts", self.arguments(mutation)))
                    self.assertEqual(report["status"], "BLOCKED")
                    self.assertTrue(report["issues"])
                    self.assertFalse(report["purchase_authorized"])
                    self.assertFalse((Path(report["receipt_dir"]) / "digikey.csv").exists())
                    self.assertTrue((Path(report["receipt_dir"]) / "report.json").is_file())

    async def test_invalid_paths_and_saved_runner_fail_before_creating_receipts(self) -> None:
        outside = self.base / "outside.json"
        write_model(outside, PurchasingPreferences())
        linked = self.root / "build/linked.json"
        linked.symlink_to(outside)
        peer = self.root / "examples/projects/arduino-uno-status-led/docs/purchasing.json"
        write_model(peer, PurchasingPreferences())
        invalid = (
            {"view_id": "../escape"}, {"view_id": "/tmp/escape"},
            {"native_summary": "../outside.json"}, {"native_summary": str(self.native / "summary.json")},
            {"native_summary": "catalog/parts.json"}, {"preferences": "build/linked.json"},
            {"preferences": peer.relative_to(self.root).as_posix()},
            {"preferences": "catalog/parts.json"}, {"preferences": "../outside.json"},
            {"runner": "local"}, {"runner": "container"},
        )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            for update in invalid:
                with self.subTest(update=update):
                    result = await client.call_tool("prepare_parts", self.arguments() | update)
                    self.assertTrue(result.is_error, result.content)
                    self.assertFalse((self.root / "build/parts").exists())
            for sibling in ("netlist.xml", "netlist.command.json"):
                path = self.native / sibling
                original = path.read_bytes()
                path.unlink()
                path.symlink_to(outside)
                result = await client.call_tool("prepare_parts", self.arguments())
                self.assertTrue(result.is_error, result.content)
                self.assertFalse((self.root / "build/parts").exists())
                path.unlink()
                path.write_bytes(original)

    async def test_alternate_preferences_are_bounded_and_run_overrides_do_not_rewrite(self) -> None:
        saved = PurchasingPreferences(boards=4, digikey_skus={"resistor-1k": "541-1KABC-ND"})
        write_model(self.preferences_path, saved)
        alternate = self.island / "docs/pilot.json"
        write_model(alternate, PurchasingPreferences(boards=7))
        temporary = self.root / "build/preferences.json"
        write_model(temporary, PurchasingPreferences(boards=9))
        original = self.preferences_path.read_bytes()
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            for index, (path, expected) in enumerate(((None, 4), (alternate, 7), (temporary, 9))):
                arguments = self.arguments(f"preferences-{index}")
                if path is not None:
                    arguments["preferences"] = path.relative_to(self.root).as_posix()
                report = self.structured(await client.call_tool("prepare_parts", arguments))
                self.assertEqual(report["plan"]["preferences"]["boards"], expected)
            report = self.structured(await client.call_tool("prepare_parts", self.arguments("override") | {"boards": 10}))
            self.assertEqual(report["plan"]["preferences"]["boards"], 10)
            self.assertEqual(report["plan"]["lines"][0]["order_number"], "541-1KABC-ND")
        self.assertEqual(self.preferences_path.read_bytes(), original)

    async def test_fresh_capture_uses_only_fixed_runner_with_both_capabilities(self) -> None:
        constructors = {"auto": "AutoNetlistRunner", "local": "LocalNetlistRunner",
                        "container": "ContainerNetlistRunner"}
        async with Client(create_server(self.root, allow_exports=True, allow_checks=True), mode="legacy") as client:
            for selection, constructor in constructors.items():
                with self.subTest(runner=selection):
                    runner = parts_fixture.FixtureRunner()
                    if selection == "container":
                        runner.selected_runner = "container"
                    with patch(f"kicad_tooling.hwrepo.mcp_parts.contract_coach.{constructor}", return_value=runner) as factory:
                        report = self.structured(await client.call_tool("prepare_parts", {
                            "project_id": self.project_id, "view_id": f"fresh-{selection}",
                            "runner": selection,
                        }))
                        factory.assert_called_once_with(*(() if selection == "container" else ("kicad-cli",)))
                    self.assertEqual(report["status"], "READY_FOR_ORDER_REVIEW", report["issues"])
                    self.assertFalse(report["purchase_authorized"])
                    self.assertEqual(report["selected_runner"], "container" if selection == "container" else "local")
                    self.assertTrue((Path(report["receipt_dir"]) / "netlist.command.json").is_file())

    async def test_preferences_create_update_and_stale_digest_preserve_exact_readback(self) -> None:
        async with Client(create_server(self.root, allow_edits=True), mode="legacy") as client:
            options = {"project_id": self.project_id, "preferences": {"boards": 3}}
            nonexistent = await client.call_tool("save_parts_preferences", options | {"expected_sha256": "0" * 64})
            self.assertTrue(nonexistent.is_error)
            self.assertFalse(self.preferences_path.exists())
            created = self.structured(await client.call_tool("save_parts_preferences", options))
            self.assertEqual(created["status"], "CREATED")
            self.assertEqual(created["path"], self.preferences_path.relative_to(self.root).as_posix())
            self.assertEqual(created["after_sha256"], created["readback_sha256"])
            self.assertFalse(created["purchase_authorized"])
            read = self.structured(await client.call_tool("read_project_file", {
                "project_id": self.project_id, "path": "docs/purchasing.json",
            }))
            self.assertEqual(read["sha256"], created["after_sha256"])
            updated = self.structured(await client.call_tool("save_parts_preferences", {
                "project_id": self.project_id, "preferences": {"boards": 6, "spare_minimum": 2},
                "expected_sha256": read["sha256"],
            }))
            self.assertEqual(updated["status"], "UPDATED")
            self.assertEqual(updated["before_sha256"], read["sha256"])
            self.assertEqual(updated["readback_sha256"], digest(self.preferences_path))
            self.assertEqual(read_model(self.preferences_path, PurchasingPreferences).boards, 6)
            before = self.preferences_path.read_bytes()
            for expected in (None, read["sha256"]):
                rejected = await client.call_tool("save_parts_preferences", options | {"expected_sha256": expected})
                self.assertTrue(rejected.is_error)
                self.assertEqual(self.preferences_path.read_bytes(), before)

    async def test_preferences_and_text_edits_enforce_typed_schema(self) -> None:
        async with Client(create_server(self.root, allow_edits=True), mode="legacy") as client:
            for preferences in ({"boards": 0}, {"boards": True}, {"spare_percent": 101},
                                {"schema_version": "2"}, {"supplier": "unreviewed"}):
                rejected = await client.call_tool("save_parts_preferences", {
                    "project_id": self.project_id, "preferences": preferences,
                })
                self.assertTrue(rejected.is_error, rejected.content)
                self.assertFalse(self.preferences_path.exists())
            self.structured(await client.call_tool("save_parts_preferences", {
                "project_id": self.project_id, "preferences": {"boards": 3},
            }))
            read = self.structured(await client.call_tool("read_project_file", {
                "project_id": self.project_id, "path": "docs/purchasing.json",
            }))
            options = {"project_id": self.project_id, "path": "docs/purchasing.json",
                       "expected_sha256": read["sha256"], "old_text": read["text"],
                       "new_text": '{"schema_version":"1","boards":0}'}
            for tool in ("preview_project_edit", "apply_project_edit"):
                rejected = await client.call_tool(tool, options)
                self.assertTrue(rejected.is_error, rejected.content)
            self.assertEqual(digest(self.preferences_path), read["sha256"])
            options["new_text"] = PurchasingPreferences(boards=4).model_dump_json(indent=2) + "\n"
            self.structured(await client.call_tool("preview_project_edit", options))
            self.structured(await client.call_tool("apply_project_edit", options))
            self.assertEqual(read_model(self.preferences_path, PurchasingPreferences).boards, 4)

    async def test_preferences_symlink_cannot_write_outside_selected_island(self) -> None:
        outside = self.base / "preferences.json"
        write_model(outside, PurchasingPreferences(boards=2))
        self.preferences_path.symlink_to(outside)
        before = outside.read_bytes()
        async with Client(create_server(self.root, allow_edits=True), mode="legacy") as client:
            result = await client.call_tool("save_parts_preferences", {
                "project_id": self.project_id, "preferences": {"boards": 3},
                "expected_sha256": digest(outside),
            })
            self.assertTrue(result.is_error)
        self.assertEqual(outside.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
