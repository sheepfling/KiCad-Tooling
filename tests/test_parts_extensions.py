"""Actual CLI/protocol parity and authority guards for reviewed parts extensions.

Native evidence and external HTTP replies are synthetic. No supplier submission
or CAD download reaches the network, and none of these fixtures approves hardware.
"""
from __future__ import annotations

import asyncio
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

from mcp import Client
from pydantic import BaseModel, ValidationError

from kicad_tooling.hwrepo import mcp_parts_extensions, part_picker, supplier_handoff
from kicad_tooling.hwrepo.cad_download import fetch_official_footprint
from kicad_tooling.hwrepo.contracts import parse_model_text, read_model, write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    AutoCadPlan,
    AutoCadReport,
    CheckEvidence,
    PartPickerReport,
    PartSelectionAssignment,
    PartSelectionMap,
    PartSelectionReport,
    ProjectKind,
    PurchasingReport,
    SupplierHandoffPlan,
    SupplierHandoffReport,
    ValidationSummary,
)
from kicad_tooling.hwrepo.parts_workflow import save_report
from kicad_tooling.validate import hashes
from tests import test_cad_download as download_fixture
from tests import test_part_picker as picker_fixture
from tests import test_parts_workflow as parts_fixture
from tests.support import SOURCE_ROOT, reference_root
from tests.test_cad_assets import FOOTPRINT, TRANSFORM, board

_REVIEW_URL = "https://www.digikey.com/short/abc1234"


class PartsExtensionsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="parts-extensions-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "repository"
        shutil.copytree(reference_root(), self.root,
                        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"))

    def use_picker(self) -> None:
        fixture = picker_fixture.PartPickerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.picker_fixture = fixture
        self.saved_native(picker_fixture.NETLIST)

    def use_order(self) -> PurchasingReport:
        fixture = parts_fixture.PartsWorkflowTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.parts_fixture = fixture
        report = fixture.review(boards=4, spare_percent=10, spare_minimum=3)
        self.assertEqual(report.status, "READY_FOR_ORDER_REVIEW", report.issues)
        self.assertEqual(report.native_status, "FAIL")
        save_report(Path(report.receipt_dir), report)
        self.order_path = (Path(report.receipt_dir) / "report.json").relative_to(self.root).as_posix()
        return report

    def saved_native(self, netlist: str) -> None:
        native = self.root / "build/native/controller"
        native.mkdir(parents=True, exist_ok=True)
        (native / "netlist.xml").write_text(netlist, encoding="utf-8")
        write_model(native / "netlist.command.json", parts_fixture.command())
        config = load_config(self.root, "examples/projects/controller/project.json")
        current = hashes(self.root, config.source_roots)
        write_model(native / "summary.json", ValidationSummary(
            timestamp_utc="2026-09-24T00:00:00+00:00", checked_commit="LOCAL_UNBOUND",
            project_id="controller", project_kind=ProjectKind.PCB,
            checks={
                "source_scope": CheckEvidence(status="PASS", source_hashes=current),
                "source_unchanged": CheckEvidence(status="PASS", source_hashes=current),
                "toolchain": CheckEvidence(status="PASS", observed_version=config.kicad_version,
                                           image=config.image),
                "netlist": CheckEvidence(status="FAIL", returncode=0, error="Synthetic contract mismatch"),
            }, status="FAIL", artifacts_sha256={
                "netlist.xml": digest(native / "netlist.xml"),
                "netlist.command.json": digest(native / "netlist.command.json"),
            },
        ))

    async def cli(self, model, *arguments, expected_exit=0, stub_http=False):
        command = [sys.executable, "-B", "-m", "kicad_tooling.parts"]
        if stub_http:
            # Only the external HTTP exchange is replaced. CLI parsing, persisted
            # review validation, attempt recording and response checks run normally.
            script = (
                "import runpy,sys; from unittest.mock import patch; "
                "sys.argv=['kicad_tooling.parts',*sys.argv[1:]]; "
                "p=patch('kicad_tooling.hwrepo.digikey_handoff._post',return_value="
                + repr(json.dumps(_REVIEW_URL).encode())
                + "); p.start(); runpy.run_module('kicad_tooling.parts',run_name='__main__')"
            )
            command = [sys.executable, "-B", "-c", script]
        process = await asyncio.to_thread(
            subprocess.run,
            (*command, "--root", str(self.root), "--project", "controller", *arguments, "--format", "json"),
            cwd=self.base, env={**os.environ, "PYTHONPATH": str(SOURCE_ROOT)},
            text=True, capture_output=True, check=False, timeout=60,
        )
        self.assertEqual(process.returncode, expected_exit, process.stderr + process.stdout)
        return parse_model_text(process.stdout, model)

    async def call(self, client, name, model, **arguments):
        result = await client.call_tool(name, arguments)
        self.assertFalse(result.is_error, result.content)
        self.assertIsNotNone(result.structured_content)
        return model.model_validate_json(json.dumps(result.structured_content))

    @staticmethod
    def semantic(report: BaseModel, *paths: str):
        text = report.model_dump_json()
        for path in paths:
            text = text.replace(path, "<receipt>")
        return json.loads(text)

    def sources(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()
                and path.relative_to(self.root).parts[0] != "build"}

    def restore_sources(self, before):
        for name in self.sources().keys() - before.keys():
            (self.root / name).unlink()
        for name, content in before.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    async def test_picker_selection_and_sync_cli_protocol_parity(self) -> None:
        self.use_picker()
        summary = "build/native/controller/summary.json"
        cli_picker = await self.cli(PartPickerReport, "--picker", "--native-summary", summary,
                                    "--output", "build/parts/cli-picker")
        server = create_server(self.root, allow_exports=True, allow_edits=True)
        async with Client(server) as client:
            picker = await self.call(client, "prepare_part_picker", PartPickerReport,
                project_id="controller", view_id="mcp-picker", native_summary=summary)
            self.assertEqual(picker.status, "READY", picker.issues)
            self.assertEqual(self.semantic(cli_picker, cli_picker.receipt_dir),
                             self.semantic(picker, picker.receipt_dir))
            assert picker.evidence is not None
            self.assertEqual(picker.evidence.native_status, "FAIL")
            draft = self.picker_fixture.draft(cli_picker)
            before = self.sources()
            cli_preview = await self.cli(PartSelectionReport, "--selection", str(draft),
                                         "--output", "build/parts/cli-selection")
            preview = await self.call(client, "preview_part_selection", PartSelectionReport,
                project_id="controller", view_id="mcp-selection",
                picker_report="build/parts/mcp-picker/report.json",
                assignments=[{"reference": "R1", "part_id": "test-r1"}])
            self.assertEqual(preview.status, "PLAN", preview.issues)
            self.assertEqual(self.semantic(cli_preview, cli_preview.receipt_dir),
                             self.semantic(preview, preview.receipt_dir))
            self.assertEqual(self.sources(), before)
            preferences_edit = next(item for item in preview.edits if item.path.endswith("purchasing.json"))
            self.assertIsNone(preferences_edit.before)
            assert cli_preview.locked_map is not None and preview.locked_map is not None
            cli_applied = await self.cli(PartSelectionReport, "--selection", cli_preview.locked_map,
                                         "--apply", "--output", "build/parts/cli-apply")
            cli_sources = self.sources()
            self.restore_sources(before)
            applied = await self.call(client, "apply_part_selection", PartSelectionReport,
                project_id="controller", view_id="mcp-apply",
                selection_map=Path(preview.locked_map).relative_to(self.root).as_posix(),
                expected_sha256=digest(Path(preview.locked_map)))
            self.assertEqual(applied.status, "APPLIED", applied.issues)
            self.assertEqual(self.semantic(cli_applied, cli_applied.receipt_dir),
                             self.semantic(applied, applied.receipt_dir))
            self.assertEqual(self.sources(), cli_sources)
            cli_sync = await self.cli(PartSelectionReport, "--sync-models", "--output", "build/parts/cli-sync")
            sync = await self.call(client, "preview_model_sync", PartSelectionReport,
                                  project_id="controller", view_id="mcp-sync")
            self.assertEqual(self.semantic(cli_sync, cli_sync.receipt_dir), self.semantic(sync, sync.receipt_dir))

    async def test_picker_and_edit_capabilities_and_stale_evidence(self) -> None:
        self.use_picker()
        async with Client(create_server(self.root)) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            self.assertFalse({"prepare_part_picker", "apply_part_selection", "submit_supplier_handoff"} & names)
        async with Client(create_server(self.root, allow_exports=True)) as client:
            with patch("kicad_tooling.hwrepo.contract_coach.capture") as capture:
                refused = await client.call_tool("prepare_part_picker", {"project_id": "controller", "view_id": "no-native"})
            self.assertTrue(refused.is_error)
            capture.assert_not_called()
            self.picker_fixture.schematic.write_bytes(self.picker_fixture.schematic.read_bytes() + b"\n")
            cli = await self.cli(PartPickerReport, "--picker", "--native-summary", "build/native/controller/summary.json",
                                 "--output", "build/parts/cli-stale", expected_exit=1)
            stale = await self.call(client, "prepare_part_picker", PartPickerReport,
                project_id="controller", view_id="mcp-stale", native_summary="build/native/controller/summary.json")
            self.assertEqual(stale.status, "BLOCKED")
            self.assertEqual(self.semantic(cli, cli.receipt_dir), self.semantic(stale, stale.receipt_dir))
            escaped = await client.call_tool("prepare_part_picker", {"project_id": "controller", "view_id": "escape",
                "native_summary": str(self.root / "build/native/controller/summary.json")})
            self.assertTrue(escaped.is_error)

    async def test_auto_cad_cli_protocol_parity(self) -> None:
        member = self.base / "installed/footprints/Paired.pretty/TwoPin.kicad_mod"
        member.parent.mkdir(parents=True)
        member.write_text(FOOTPRINT, encoding="utf-8")
        model = self.base / "installed/3dmodels/Paired.3dshapes/TwoPin.step"
        model.parent.mkdir(parents=True)
        model.write_bytes(b"ISO-10303-21;\nSYNTHETIC ONLY\nEND-ISO-10303-21;\n")
        pcb = self.root / "examples/projects/controller/kicad/controller.kicad_pcb"
        pcb.write_text(board(90, True), encoding="utf-8")
        before = self.sources()
        with patch.dict(os.environ, {"KICAD10_FOOTPRINT_DIR": str(member.parent.parent),
                                     "KICAD10_3DMODEL_DIR": str(model.parent.parent)}):
            cli_preview = await self.cli(AutoCadReport, "--auto-models", "--output", "build/parts/cli-cad")
            async with Client(create_server(self.root, allow_exports=True, allow_edits=True)) as client:
                preview = await self.call(client, "preview_auto_cad", AutoCadReport,
                                         project_id="controller", view_id="mcp-cad")
                self.assertEqual(preview.status, "PLAN", preview.issues)
                self.assertEqual(self.semantic(cli_preview, cli_preview.receipt_directory),
                                 self.semantic(preview, preview.receipt_directory))
                self.assertEqual(self.sources(), before)
                assert cli_preview.plan_path is not None and preview.plan_path is not None
                cli_applied = await self.cli(AutoCadReport, "--cad-plan", cli_preview.plan_path,
                                             "--apply", "--output", "build/parts/cli-cad-apply")
                expected = self.sources()
                self.restore_sources(before)
                reviewed_path = Path(preview.plan_path)
                reviewed_sha = digest(reviewed_path)
                invalid_map = read_model(reviewed_path, AutoCadPlan).model_copy(
                    update={"after_hashes": {"README.md": "0" * 64}})
                original_output = mcp_parts_extensions._output

                def replace_after_hash(root, view_id):
                    write_model(reviewed_path, invalid_map)
                    return original_output(root, view_id)

                with patch("kicad_tooling.hwrepo.mcp_parts_extensions._output", side_effect=replace_after_hash):
                    applied = await self.call(client, "apply_auto_cad", AutoCadReport,
                        project_id="controller", view_id="mcp-cad-apply",
                        plan=reviewed_path.relative_to(self.root).as_posix(), expected_sha256=reviewed_sha)
                self.assertEqual(applied.status, "APPLIED", applied.issues)
                self.assertEqual(self.semantic(cli_applied, cli_applied.receipt_directory),
                                 self.semantic(applied, applied.receipt_directory))
                self.assertEqual(self.sources(), expected)
                self.assertIn(TRANSFORM, pcb.read_text())
                stale = await client.call_tool("apply_auto_cad", {
                    "project_id": "controller", "view_id": "bad-digest",
                    "plan": Path(preview.plan_path).relative_to(self.root).as_posix(), "expected_sha256": "0" * 64})
                self.assertTrue(stale.is_error)

    async def test_download_permission_and_cache_symlink_boundaries(self) -> None:
        cache = self.root / "build/cad-cache"
        with patch("kicad_tooling.hwrepo.cad_download._download") as transfer:
            with self.assertRaisesRegex(ValueError, "allow-downloads"):
                fetch_official_footprint(cache, "Library:Exact_Name", "10.0.5", allow_downloads=False)
            transfer.assert_not_called()
        fixture = download_fixture.CadDownloadTests()
        fixture.urls = []
        with patch("kicad_tooling.hwrepo.cad_download._download", side_effect=fixture.download):
            cached = fetch_official_footprint(cache, "Library:Exact_Name", "10.0.5")
        with patch("kicad_tooling.hwrepo.cad_download._download") as transfer:
            self.assertEqual(fetch_official_footprint(cache, "Library:Exact_Name", "10.0.5",
                                                      allow_downloads=False), cached)
            transfer.assert_not_called()
        outside = self.base / "outside"
        outside.mkdir()
        for relative in ("build/cache-link", "linked-build/cache"):
            linked = self.root / relative
            link = linked if relative.startswith("build/") else linked.parent
            link.symlink_to(outside, target_is_directory=True)
            with patch("kicad_tooling.hwrepo.cad_download._download") as transfer:
                with self.assertRaisesRegex(ValueError, "symlink"):
                    fetch_official_footprint(linked, "Library:Exact_Name", "10.0.5")
                transfer.assert_not_called()
            link.unlink()
        self.assertEqual(list(outside.iterdir()), [])
        version_cache = self.root / "build/version-cache"
        version_cache.mkdir()
        (version_cache / "kicad-10.0.5").symlink_to(cache / "kicad-10.0.5", target_is_directory=True)
        with patch("kicad_tooling.hwrepo.cad_download._download") as transfer:
            with self.assertRaisesRegex(ValueError, "symlink"):
                fetch_official_footprint(version_cache, "Library:Exact_Name", "10.0.5", allow_downloads=False)
            transfer.assert_not_called()
        pcb = self.root / "examples/projects/controller/kicad/controller.kicad_pcb"
        pcb.write_text(board().replace("Paired:TwoPin", "MissingTestOnly:Missing"))
        with patch("kicad_tooling.hwrepo.cad_download._download") as transfer:
            async with Client(create_server(self.root, allow_exports=True)) as client:
                report = await self.call(client, "preview_auto_cad", AutoCadReport,
                                         project_id="controller", view_id="no-download")
            transfer.assert_not_called()
        self.assertEqual(report.status, "NEEDS_REVIEW")
        self.assertIn("allow-downloads", " ".join(report.issues))

    async def test_supplier_prepare_and_submit_cli_protocol_parity(self) -> None:
        order = self.use_order()
        with patch("kicad_tooling.hwrepo.digikey_handoff._post", side_effect=AssertionError("offline preparation")):
            cli = await self.cli(SupplierHandoffReport, "--prepare-handoff", self.order_path,
                                 "--output", "build/supplier-handoffs/cli")
            async with Client(create_server(self.root, allow_exports=True)) as client:
                prepared = await self.call(client, "prepare_supplier_handoff", SupplierHandoffReport,
                    project_id="controller", view_id="mcp", parts_report=self.order_path)
        self.assertEqual(self.semantic(cli, cli.handoff), self.semantic(prepared, prepared.handoff))
        cli_plan = read_model(self.root / cli.handoff, SupplierHandoffPlan)
        plan = read_model(self.root / prepared.handoff, SupplierHandoffPlan)
        self.assertEqual(cli_plan, plan)
        self.assertEqual(plan.source_hashes, order.source_hashes)
        self.assertEqual(digest((self.root / prepared.handoff).parent / "payload.json"), prepared.payload_sha256)
        self.assertEqual(plan.payload_sha256, hashlib.sha256(plan.payload.model_dump_json(by_alias=True).encode()).hexdigest())
        # Independent copies run both complete submission paths while retaining
        # byte-identical source/review contracts and a separate attempt ledger.
        protocol_root = self.root
        cli_root = self.base / "cli-submission"
        shutil.copytree(protocol_root, cli_root)
        self.root = cli_root
        cli_result = await self.cli(SupplierHandoffReport, "--submit-handoff", cli.handoff,
            "--expected-sha256", cli.handoff_sha256, "--allow-supplier-submissions", stub_http=True)
        self.root = protocol_root
        with patch("kicad_tooling.hwrepo.digikey_handoff._post", return_value=json.dumps(_REVIEW_URL).encode()) as post:
            async with Client(create_server(self.root, allow_supplier_submissions=True)) as client:
                result = await self.call(client, "submit_supplier_handoff", SupplierHandoffReport,
                    handoff=prepared.handoff, expected_sha256=prepared.handoff_sha256)
            self.assertEqual(post.call_count, 1)
        self.assertEqual(self.semantic(result, result.handoff), self.semantic(cli_result, cli_result.handoff))
        # A copied handle in the same checkout shares the durable attempt digest.
        with patch("kicad_tooling.hwrepo.digikey_handoff._post", side_effect=AssertionError("must not resubmit")):
            async with Client(create_server(self.root, allow_supplier_submissions=True)) as client:
                repeated = await self.call(client, "submit_supplier_handoff", SupplierHandoffReport,
                    handoff=cli.handoff, expected_sha256=cli.handoff_sha256)
        self.assertEqual(repeated.handoff, cli.handoff)
        self.assertEqual(self.semantic(repeated, repeated.handoff), self.semantic(result, result.handoff))
        self.assertEqual(result.status, "SENT")
        self.assertEqual(result.single_use_url, _REVIEW_URL)
        self.assertFalse(result.purchase_authorized)
        self.assertFalse(result.build_authorized)

    async def prepared_handoff(self, view_id="review") -> SupplierHandoffReport:
        async with Client(create_server(self.root, allow_exports=True)) as client:
            return await self.call(client, "prepare_supplier_handoff", SupplierHandoffReport,
                project_id="controller", view_id=view_id, parts_report=self.order_path)

    async def test_supplier_capability_digest_and_stale_review_reject_before_network(self) -> None:
        self.use_order()
        prepared = await self.prepared_handoff()
        arguments = {"handoff": prepared.handoff, "expected_sha256": prepared.handoff_sha256}
        async with Client(create_server(self.root, allow_exports=True, allow_edits=True, allow_checks=True)) as client:
            self.assertNotIn("submit_supplier_handoff", {tool.name for tool in (await client.list_tools()).tools})
            self.assertTrue((await client.call_tool("submit_supplier_handoff", arguments)).is_error)
        with patch("kicad_tooling.hwrepo.digikey_handoff._post") as post:
            async with Client(create_server(self.root, allow_supplier_submissions=True)) as client:
                self.assertTrue((await client.call_tool("submit_supplier_handoff",
                    {**arguments, "expected_sha256": "0" * 64})).is_error)
                schematic = self.parts_fixture.island / "kicad/controller.kicad_sch"
                schematic.write_bytes(schematic.read_bytes() + b"\n")
                self.assertTrue((await client.call_tool("submit_supplier_handoff", arguments)).is_error)
            post.assert_not_called()
        self.assertFalse((self.root / "build/supplier-submissions").exists())

    async def test_supplier_uncertain_attempt_is_persistent_and_never_retried(self) -> None:
        self.use_order()
        prepared = await self.prepared_handoff()
        arguments = {"handoff": prepared.handoff, "expected_sha256": prepared.handoff_sha256}
        with patch("kicad_tooling.hwrepo.digikey_handoff._post", side_effect=OSError("synthetic disconnect")) as post:
            async with Client(create_server(self.root, allow_supplier_submissions=True)) as client:
                result = await self.call(client, "submit_supplier_handoff", SupplierHandoffReport, **arguments)
            self.assertEqual(post.call_count, 1)
        self.assertEqual(result.status, "UNCERTAIN")
        assert result.attempt_receipt is not None
        self.assertEqual(read_model(self.root / result.attempt_receipt, SupplierHandoffReport), result)
        with patch("kicad_tooling.hwrepo.digikey_handoff._post", side_effect=AssertionError("must never retry")) as post:
            async with Client(create_server(self.root, allow_supplier_submissions=True)) as client:
                again = await self.call(client, "submit_supplier_handoff", SupplierHandoffReport, **arguments)
            post.assert_not_called()
        self.assertEqual(again, result)

    async def test_supplier_attempt_is_reserved_before_post_and_source_drift_remains_blocked(self) -> None:
        self.use_order()
        prepared = await self.prepared_handoff()
        reserved = []

        def external_reply(path, body):
            reserved.append(supplier_handoff.submit_supplier_handoff(
                self.root, prepared.handoff, prepared.handoff_sha256))
            schematic = self.parts_fixture.island / "kicad/controller.kicad_sch"
            schematic.write_bytes(schematic.read_bytes() + b"\n")
            return json.dumps(_REVIEW_URL).encode()

        with patch("kicad_tooling.hwrepo.digikey_handoff._post", side_effect=external_reply) as post:
            async with Client(create_server(self.root, allow_supplier_submissions=True)) as client:
                result = await self.call(client, "submit_supplier_handoff", SupplierHandoffReport,
                    handoff=prepared.handoff, expected_sha256=prepared.handoff_sha256)
            self.assertEqual(post.call_count, 1)
        self.assertEqual(reserved[0].status, "UNCERTAIN")
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("may already have received", " ".join(result.issues))
        self.assertFalse(result.purchase_authorized)

    async def test_part_apply_uses_reviewed_bytes_when_original_map_is_swapped(self) -> None:
        self.use_picker()
        fixture = self.picker_fixture
        alternate = fixture.part.model_copy(update={"id": "test-r1-alternate", "mpn": "TEST-ALTERNATE"})
        fixture.set_parts(fixture.part, alternate)
        draft = fixture.draft()
        first = part_picker.selection(self.root, "controller", draft, fixture.receipt())
        spec = read_model(draft, PartSelectionMap)
        write_model(draft, spec.model_copy(update={"assignments": (
            PartSelectionAssignment(reference="R1", part_id=alternate.id),)}))
        second = part_picker.selection(self.root, "controller", draft, fixture.receipt())
        self.assertEqual((first.status, second.status), ("PLAN", "PLAN"))
        assert first.locked_map is not None and second.locked_map is not None
        original = Path(first.locked_map)
        expected_sha = digest(original)
        replacement = Path(second.locked_map).read_bytes()
        original_output = mcp_parts_extensions._output

        def swap_after_review(root, view_id):
            original.write_bytes(replacement)
            return original_output(root, view_id)

        with patch("kicad_tooling.hwrepo.mcp_parts_extensions._output", side_effect=swap_after_review):
            async with Client(create_server(self.root, allow_edits=True)) as client:
                applied = await self.call(client, "apply_part_selection", PartSelectionReport,
                    project_id="controller", view_id="swap-apply",
                    selection_map=original.relative_to(self.root).as_posix(), expected_sha256=expected_sha)
        self.assertEqual(applied.status, "APPLIED", applied.issues)
        from kicad_tooling.hwrepo.part_cad import read_cad_components
        self.assertEqual(read_cad_components(self.root, "controller")[0].part_id, fixture.part.id)

    async def test_supplier_digest_race_cannot_substitute_another_valid_payload(self) -> None:
        self.use_order()
        first = await self.prepared_handoff("first")
        second_order = self.parts_fixture.review(boards=11)
        save_report(Path(second_order.receipt_dir), second_order)
        self.order_path = (Path(second_order.receipt_dir) / "report.json").relative_to(self.root).as_posix()
        second = await self.prepared_handoff("second")
        path = self.root / first.handoff
        first_bytes = path.read_bytes()
        second_bytes = (self.root / second.handoff).read_bytes()
        first_spec = read_model(path, SupplierHandoffPlan)
        calls = 0

        def swap_around_digest(candidate):
            nonlocal calls
            if candidate != path:
                return digest(candidate)
            calls += 1
            # Reproduce an ABA swap: checked digest belongs to the first plan,
            # while an unsafe subsequent path read would see the second plan.
            if calls % 2:
                observed = digest(candidate)
                path.write_bytes(second_bytes)
                return observed
            path.write_bytes(first_bytes)
            return digest(candidate)

        with (patch("kicad_tooling.hwrepo.supplier_handoff.digest", side_effect=swap_around_digest),
              patch("kicad_tooling.hwrepo.digikey_handoff._post", return_value=json.dumps(_REVIEW_URL).encode()) as post):
            async with Client(create_server(self.root, allow_supplier_submissions=True)) as client:
                result = await client.call_tool("submit_supplier_handoff", {
                    "handoff": first.handoff, "expected_sha256": first.handoff_sha256})
        self.assertGreater(calls, 0)
        for call in post.call_args_list:
            self.assertEqual(call.args[1], first_spec.payload.model_dump_json(by_alias=True).encode())
        if not result.is_error:
            retained = SupplierHandoffReport.model_validate_json(json.dumps(result.structured_content))
            self.assertIn(retained.status, {"SENT", "BLOCKED", "UNCERTAIN"})

    async def test_supplier_existing_attempt_rejects_fifo_and_oversized_receipts(self) -> None:
        self.use_order()
        prepared = await self.prepared_handoff()
        receipt = self.root / f"build/supplier-submissions/{prepared.handoff_sha256}.json"
        receipt.parent.mkdir()
        variants = ["oversized"] + (["fifo"] if hasattr(os, "mkfifo") else [])
        async with Client(create_server(self.root, allow_supplier_submissions=True)) as client:
            for variant in variants:
                with self.subTest(variant=variant):
                    if variant == "fifo":
                        os.mkfifo(receipt)
                    else:
                        receipt.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
                    with (patch("kicad_tooling.hwrepo.digikey_handoff._post") as post,
                          patch("kicad_tooling.hwrepo.supplier_handoff.read_model", wraps=read_model) as reader):
                        result = await client.call_tool("submit_supplier_handoff", {
                            "handoff": prepared.handoff, "expected_sha256": prepared.handoff_sha256})
                        self.assertTrue(result.is_error)
                        post.assert_not_called()
                        self.assertFalse(any(call.args[0] == receipt for call in reader.call_args_list))
                    receipt.unlink()

    async def test_supplier_contracts_and_tampered_projection_reject(self) -> None:
        self.use_order()
        prepared = await self.prepared_handoff()
        spec = read_model(self.root / prepared.handoff, SupplierHandoffPlan)
        for record in (prepared, spec):
            model = type(record)
            self.assertEqual(model.model_validate_json(record.model_dump_json()), record)
            for mutation in ({"schema_version": 2}, {"unknown": True}, {"project_id": 3},
                             {"payload_sha256": "wrong"}, {"purchase_authorized": True}):
                raw = record.model_dump(mode="json") | mutation
                with self.subTest(model=model, mutation=mutation), self.assertRaises(ValidationError):
                    model.model_validate_json(json.dumps(raw))
        for invalid_url in ("https://example.invalid/short/abc1234", "http://www.digikey.com/short/abc1234",
                            "https://www.digikey.com/short/abc1234?track=1"):
            with self.subTest(invalid_url=invalid_url), self.assertRaises(ValidationError):
                SupplierHandoffReport.model_validate_json(json.dumps(
                    prepared.model_dump(mode="json") | {"single_use_url": invalid_url}))
        report_path = self.root / self.order_path
        order = read_model(report_path, PurchasingReport)
        assert order.plan is not None
        changed_line = order.plan.lines[0].model_copy(update={"quantity": 999})
        write_model(report_path, order.model_copy(update={"plan": order.plan.model_copy(update={"lines": (changed_line,)})}))
        with patch("kicad_tooling.hwrepo.digikey_handoff._post") as post:
            async with Client(create_server(self.root, allow_exports=True)) as client:
                result = await client.call_tool("prepare_supplier_handoff", {
                    "project_id": "controller", "view_id": "tampered", "parts_report": self.order_path})
            self.assertTrue(result.is_error)
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
