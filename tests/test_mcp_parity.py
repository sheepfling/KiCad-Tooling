"""Behavioral CLI/MCP parity using subprocess CLIs and the real MCP protocol.

Fixtures use small authored examples and explicitly synthetic retained native
netlists. No shared service is mocked. Comparison preserves domain statuses,
findings, identities, quantities, hashes and actions; only receipt paths, command
start timestamps and unittest's measured elapsed time are normalized.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client
from pydantic import BaseModel

from kicad_tooling.hwrepo.contracts import parse_model_text, read_model, write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    CheckAllSummary,
    CheckEvidence,
    ComponentIdentity,
    ContractCoachReport,
    DiagnosticReport,
    ImportInventoryReport,
    LocalRescueReport,
    McpPurchasingPreferencesResult,
    ModelInventoryReport,
    PartRecord,
    PartsCatalog,
    PartStatus,
    ProjectImportReport,
    ProjectKind,
    ProjectManifest,
    ProjectScaffoldReport,
    ProjectStaticPipelineReport,
    ProjectVerificationReport,
    PurchasingPreferences,
    PurchasingReport,
    TemplateDoctorReport,
    TemplateInventoryReport,
    ThreeDReport,
    ValidationSummary,
)
from kicad_tooling.validate import hashes
from tests import test_parts_workflow as native_fixture
from tests.support import initialize_git, reference_root


class McpParityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="mcp-semantic-parity-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "repository"
        shutil.copytree(
            reference_root(),
            self.root,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        initialize_git(self.root)
        self.island = self.root / "examples/projects/controller"
        self.incoming = self.root / "build/incoming/Incoming board.kicad_pro"
        self.incoming.parent.mkdir(parents=True)
        self.incoming.write_text("{}", encoding="utf-8")
        self.incoming.with_suffix(".kicad_sch").write_text("(kicad_sch)", encoding="utf-8")
        self.incoming.with_suffix(".kicad_pcb").write_text("(kicad_pcb)", encoding="utf-8")

    async def cli_process(self, module, *arguments):
        # A foreign cwd proves --root rather than process cwd selects the board.
        process = await asyncio.to_thread(
            subprocess.run,
            (
                sys.executable,
                "-B",
                "-m",
                module,
                "--root",
                str(self.root),
                *arguments,
                "--format",
                "json",
            ),
            cwd=self.base,
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
        return process

    async def cli(self, module, model, *arguments, expected_exit=0):
        process = await self.cli_process(module, *arguments)
        self.assertEqual(process.returncode, expected_exit, process.stderr + process.stdout)
        return parse_model_text(process.stdout, model)

    async def call(self, client, tool, model, arguments=None):
        result = await client.call_tool(tool, arguments or {})
        self.assertFalse(result.is_error, result.content)
        self.assertIsNotNone(result.structured_content)
        return model.model_validate_json(json.dumps(result.structured_content))

    @staticmethod
    def semantic(report: BaseModel, receipt: str | None = None):
        def normalize(value, field=None):
            if isinstance(value, dict):
                return {key: normalize(item, key) for key, item in value.items()}
            if isinstance(value, list):
                return [normalize(item) for item in value]
            if isinstance(value, str):
                if field == "started_utc":
                    return "<command-start>"
                if receipt is not None:
                    value = value.replace(receipt, "<receipt>")
                if field == "stderr":
                    value = re.sub(
                        r"(?m)^(Ran \d+ tests? in )\d+(?:\.\d+)?s$", r"\1<elapsed>s", value
                    )
            return value

        return normalize(report.model_dump(mode="json"))

    def receipt_equal(self, cli, mcp, field="run_directory") -> None:
        left = getattr(cli, field)
        right = getattr(mcp, field)
        self.assertNotEqual(left, right)
        self.assertTrue(Path(left).is_relative_to(self.root / "build"))
        self.assertTrue(Path(right).is_relative_to(self.root / "build"))
        self.assertEqual(self.semantic(cli, left), self.semantic(mcp, right))

    def import_args(self):
        return {
            "source": self.incoming.relative_to(self.root).as_posix(),
            "project_id": "incoming",
            "toolchain_id": "kicad-10.0.5",
        }

    def damage_import(self) -> None:
        self.incoming.with_suffix(".kicad_sch").write_text(
            '(kicad_sch (sheet (property "Sheetfile" "missing.kicad_sch")))',
            encoding="utf-8",
        )

    def native_evidence(self) -> Path:
        """Retain a valid netlist whose independent electrical check explicitly failed."""
        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "component_identity": ComponentIdentity(
                        required=True, part_ids=("resistor-1k",)
                    ),
                }
            ),
        )
        write_model(
            self.root / "catalog/parts.json",
            PartsCatalog(
                schema_version="0.1",
                parts=(
                    PartRecord(
                        id="resistor-1k",
                        revision="A",
                        description="Synthetic parity-test identity",
                        part_class="resistor",
                        unit="each",
                        manufacturer="Vishay",
                        mpn="MRS25000C1001FCT00",
                        datasheet_url="https://example.invalid/test-only",
                        lifecycle="active",
                        status=PartStatus.APPROVED,
                    ),
                ),
            ),
        )
        config = load_config(self.root, manifest_path)
        directory = self.root / "build/native/controller"
        directory.mkdir(parents=True)
        (directory / "netlist.xml").write_text(native_fixture.NETLIST, encoding="utf-8")
        write_model(directory / "netlist.command.json", native_fixture.command())
        current = hashes(self.root, config.source_roots)
        write_model(
            directory / "summary.json",
            ValidationSummary(
                timestamp_utc="2026-09-24T00:00:00+00:00",
                checked_commit="LOCAL_UNBOUND",
                project_id="controller",
                project_kind=ProjectKind.PCB,
                checks={
                    "source_scope": CheckEvidence(status="PASS", source_hashes=current),
                    "source_unchanged": CheckEvidence(status="PASS", source_hashes=current),
                    "toolchain": CheckEvidence(
                        status="PASS", observed_version=config.kicad_version, image=config.image
                    ),
                    "netlist": CheckEvidence(
                        status="FAIL", returncode=0, error="Independent electrical contract differs"
                    ),
                },
                status="FAIL",
                artifacts_sha256={
                    "netlist.xml": digest(directory / "netlist.xml"),
                    "netlist.command.json": digest(directory / "netlist.command.json"),
                },
            ),
        )
        return directory / "summary.json"

    async def test_inventory_parity(self) -> None:
        async with Client(create_server(self.root), mode="legacy") as client:
            for broken in (False, True):
                with self.subTest(malformed_peer=broken):
                    if broken:
                        (
                            self.root / "examples/projects/passive-signal-reference/project.json"
                        ).write_text("{bad")
                    cli = await self.cli(
                        "kicad_tooling.template",
                        TemplateInventoryReport,
                        "list",
                        expected_exit=int(broken),
                    )
                    mcp = await self.call(client, "list_projects", TemplateInventoryReport)
                    self.assertEqual(cli, mcp)
                    self.assertEqual(mcp.status, "FAIL" if broken else "PASS")
                    self.assertFalse(mcp.build_authorized)

    async def test_doctor_failure_parity(self) -> None:
        # The real subprocess runner sees exactly the same unavailable environment.
        with patch.dict(os.environ, {"PATH": ""}):
            cli = await self.cli(
                "kicad_tooling.template",
                TemplateDoctorReport,
                "doctor",
                "--native",
                "--project-id",
                "controller",
                "--runner",
                "local",
                expected_exit=1,
            )
            async with Client(create_server(self.root), mode="legacy") as client:
                mcp = await self.call(
                    client,
                    "doctor",
                    TemplateDoctorReport,
                    {
                        "project_id": "controller",
                        "native": True,
                        "runner": "local",
                    },
                )
        self.assertEqual(cli, mcp)
        self.assertEqual(mcp.status, "FAIL")
        self.assertTrue(any(item.status == "FAIL" for item in mcp.checks))

    async def test_import_preview_parity(self) -> None:
        async with Client(create_server(self.root), mode="legacy") as client:
            for broken in (False, True):
                with self.subTest(missing_sheet=broken):
                    if broken:
                        self.damage_import()
                    cli = await self.cli(
                        "kicad_tooling.template",
                        ProjectImportReport,
                        "import-project",
                        "--source",
                        str(self.incoming),
                        "--project-id",
                        "incoming",
                        "--toolchain",
                        "kicad-10.0.5",
                        "--dry-run",
                        expected_exit=int(broken),
                    )
                    mcp = await self.call(
                        client, "preview_import", ProjectImportReport, self.import_args()
                    )
                    self.assertEqual(cli, mcp)
                    self.assertEqual(mcp.status, "FAIL" if broken else "PASS")
                    self.assertTrue(mcp.dry_run)
                    self.assertFalse((self.root / "projects/incoming").exists())

    async def test_import_scan_parity(self) -> None:
        (self.incoming.parent / "incomplete.kicad_pro").write_text("{}", encoding="utf-8")
        cli = await self.cli(
            "kicad_tooling.template",
            ImportInventoryReport,
            "scan-imports",
            "--source-dir",
            str(self.incoming.parent),
            "--toolchain",
            "kicad-10.0.5",
            expected_exit=1,
        )
        async with Client(create_server(self.root), mode="legacy") as client:
            mcp = await self.call(
                client,
                "scan_imports",
                ImportInventoryReport,
                {
                    "source_directory": self.incoming.parent.relative_to(self.root).as_posix(),
                    "toolchain_id": "kicad-10.0.5",
                },
            )
        self.assertEqual(cli, mcp)
        self.assertEqual(mcp.status, "NEEDS_WORK")
        self.assertEqual({item.preview.status for item in mcp.candidates}, {"PASS", "FAIL"})

    async def test_missing_electrical_requirements_are_visible_without_claiming_failure(
        self,
    ) -> None:
        cli = await self.cli(
            "kicad_tooling.template", DiagnosticReport, "diagnose", "--project-id", "controller"
        )
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            mcp = await self.call(
                client, "diagnose_project", DiagnosticReport, {"project_id": "controller"}
            )
        self.receipt_equal(cli, mcp)
        self.assertEqual(mcp.status, "PASS")
        missing = next(row for row in mcp.findings if row.code == "ELECTRICAL_NOT_CONFIGURED")
        self.assertEqual(missing.severity, "REVIEW")
        self.assertIn("--init", missing.action)
        self.assertIn("--depth electrical", missing.action)

    async def test_import_diagnosis_parity(self) -> None:
        self.damage_import()
        cli = await self.cli(
            "kicad_tooling.template",
            DiagnosticReport,
            "diagnose",
            "--source",
            str(self.incoming),
            "--project-id",
            "incoming",
            "--toolchain",
            "kicad-10.0.5",
            expected_exit=1,
        )
        async with Client(create_server(self.root), mode="legacy") as client:
            mcp = await self.call(client, "diagnose_import", DiagnosticReport, self.import_args())
        self.receipt_equal(cli, mcp)
        self.assertEqual(mcp.status, "NEEDS_WORK")
        self.assertTrue(any(item.severity == "BLOCKING" for item in mcp.findings))

    async def test_project_diagnosis_parity(self) -> None:
        (self.island / "kicad/controller.kicad_sch").unlink()
        cli = await self.cli(
            "kicad_tooling.template",
            DiagnosticReport,
            "diagnose",
            "--project-id",
            "controller",
            expected_exit=1,
        )
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            mcp = await self.call(
                client, "diagnose_project", DiagnosticReport, {"project_id": "controller"}
            )
        self.receipt_equal(cli, mcp)
        self.assertEqual(mcp.status, "NEEDS_WORK")

    async def test_rescue_parity(self) -> None:
        (self.root / "examples/projects/passive-signal-reference/project.json").write_text("{bad")
        cli = await self.cli(
            "kicad_tooling.template",
            LocalRescueReport,
            "rescue",
            "--project-id",
            "controller",
            expected_exit=1,
        )
        async with Client(create_server(self.root), mode="legacy") as client:
            mcp = await self.call(
                client, "rescue_project", LocalRescueReport, {"project_id": "controller"}
            )
        self.receipt_equal(cli, mcp)
        self.assertEqual(mcp.status, "UNVERIFIED_GLOBAL")
        self.assertFalse(mcp.ci_eligible)
        self.assertFalse(mcp.release_eligible)

    async def test_selected_verification_parity(self) -> None:
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            for broken in (False, True):
                with self.subTest(missing_source=broken):
                    if broken:
                        (self.island / "kicad/controller.kicad_sch").unlink()
                    cli = await self.cli(
                        "kicad_tooling.verify",
                        ProjectVerificationReport,
                        "--project",
                        "controller",
                        expected_exit=int(broken),
                    )
                    mcp = await self.call(
                        client,
                        "check_project",
                        ProjectVerificationReport,
                        {"project_id": "controller"},
                    )
                    self.receipt_equal(cli, mcp)
                    self.assertEqual(mcp.status, "FAIL" if broken else "PASS")
                    self.assertFalse(mcp.build_authorized)
                    if not broken:
                        self.assertIsNone(mcp.electrical)
                        self.assertIn(
                            "Full electrical analysis was not run", " ".join(mcp.next_actions)
                        )

    async def test_scope_check_parity(self) -> None:
        cli = await self.cli(
            "kicad_tooling.ci", ProjectStaticPipelineReport, "--project", "controller"
        )
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool("check_scope", {"project_ids": ["controller"]})
        self.assertFalse(result.is_error, result.content)
        self.assertIsNotNone(result.structured_content)
        mcp = ProjectStaticPipelineReport.model_validate_json(
            json.dumps(result.structured_content["report"]),
        )
        self.assertEqual(self.semantic(cli), self.semantic(mcp))
        self.assertEqual(mcp.projects, ("controller",))
        self.assertEqual(result.structured_content["status"], cli.status)
        self.assertFalse(result.structured_content["build_authorized"])

    async def test_tag_shard_scope_check_parity(self) -> None:
        cli = await self.cli(
            "kicad_tooling.ci",
            ProjectStaticPipelineReport,
            "--tag",
            "training",
            "--shard",
            "1/2",
            "--jobs",
            "2",
        )
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "check_scope", {"tags": ["training"], "shard": "1/2", "jobs": 2}
            )
        self.assertFalse(result.is_error, result.content)
        self.assertIsNotNone(result.structured_content)
        mcp = ProjectStaticPipelineReport.model_validate_json(
            json.dumps(result.structured_content["report"]),
        )
        self.assertEqual(self.semantic(cli), self.semantic(mcp))
        self.assertEqual(len(mcp.projects), 3)

    async def test_native_scope_failure_parity(self) -> None:
        # Invalid native version fails the real CLI runner before any CAD command.
        # This exercises check_all on both surfaces, not a mocked service report.
        from tests.test_contract_coach import fake_executable

        binary = self.base / "bin"
        binary.mkdir()
        fake_executable(binary / "kicad-cli", 'print("0.0.0")\n')
        with patch.dict(
            os.environ, {"PATH": str(binary) + os.pathsep + os.environ.get("PATH", "")}
        ):
            cli = await self.cli(
                "kicad_tooling.ci",
                CheckAllSummary,
                "--kicad",
                "--project",
                "controller",
                "--output",
                str(self.root / "build/native-cli"),
                expected_exit=1,
            )
            async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
                result = await client.call_tool(
                    "check_native_scope",
                    {
                        "view_id": "native-mcp",
                        "project_ids": ["controller"],
                    },
                )
        self.assertFalse(result.is_error, result.content)
        self.assertIsNotNone(result.structured_content)
        mcp = CheckAllSummary.model_validate_json(json.dumps(result.structured_content["report"]))
        self.assertEqual(cli, mcp)
        self.assertEqual(mcp.status, "FAIL")
        self.assertTrue(any(item.status == "FAIL" for item in mcp.projects))
        self.assertEqual(result.structured_content["status"], cli.status)
        self.assertFalse(result.structured_content["build_authorized"])
        cli_native = read_model(
            self.root / "build/native-cli/controller/summary.json", ValidationSummary
        )
        mcp_native = read_model(
            Path(result.structured_content["run_directory"]) / "controller/summary.json",
            ValidationSummary,
        )
        self.assertEqual(cli_native.checks, mcp_native.checks)
        self.assertEqual(cli_native.source, mcp_native.source)
        self.assertEqual(cli_native.project_id, mcp_native.project_id)
        self.assertEqual(cli_native.status, "FAIL")
        self.assertEqual(mcp_native.status, "FAIL")

    async def test_new_project_parity(self) -> None:
        cli = await self.cli(
            "kicad_tooling.template",
            ProjectScaffoldReport,
            "new-project",
            "--project-id",
            "fresh-board",
            "--kind",
            "pcb_only",
            "--toolchain",
            "kicad-10.0.5",
        )
        directory = self.root / "projects/fresh-board"
        expected_files = {
            path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob("*")
            if path.is_file()
        }
        shutil.rmtree(directory)
        async with Client(create_server(self.root, allow_writes=True), mode="legacy") as client:
            mcp = await self.call(
                client,
                "new_project",
                ProjectScaffoldReport,
                {
                    "project_id": "fresh-board",
                    "kind": "pcb_only",
                    "toolchain_id": "kicad-10.0.5",
                },
            )
        self.assertEqual(cli, mcp)
        self.assertEqual(
            expected_files,
            {
                path.relative_to(directory).as_posix(): path.read_bytes()
                for path in directory.rglob("*")
                if path.is_file()
            },
        )

    async def test_import_write_parity(self) -> None:
        cli = await self.cli(
            "kicad_tooling.template",
            ProjectImportReport,
            "import-project",
            "--source",
            str(self.incoming),
            "--project-id",
            "incoming",
            "--toolchain",
            "kicad-10.0.5",
        )
        directory = self.root / "projects/incoming"
        expected_files = {
            path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob("*")
            if path.is_file()
        }
        shutil.rmtree(directory)
        async with Client(create_server(self.root, allow_writes=True), mode="legacy") as client:
            mcp = await self.call(client, "import_project", ProjectImportReport, self.import_args())
        self.assertEqual(cli, mcp)
        self.assertFalse(mcp.dry_run)
        self.assertEqual(
            expected_files,
            {
                path.relative_to(directory).as_posix(): path.read_bytes()
                for path in directory.rglob("*")
                if path.is_file()
            },
        )

    async def test_contract_inspection_parity(self) -> None:
        native = self.native_evidence()
        async with Client(create_server(self.root), mode="legacy") as client:
            for tampered in (False, True):
                with self.subTest(tampered=tampered):
                    if tampered:
                        (native.parent / "netlist.xml").write_text("<export/>", encoding="utf-8")
                    cli = await self.cli(
                        "kicad_tooling.contract_coach",
                        ContractCoachReport,
                        "--project-id",
                        "controller",
                        "--native-summary",
                        str(native),
                        expected_exit=int(tampered),
                    )
                    mcp = await self.call(
                        client,
                        "inspect_contract",
                        ContractCoachReport,
                        {
                            "project_id": "controller",
                            "native_summary": native.relative_to(self.root).as_posix(),
                        },
                    )
                    self.assertEqual(cli, mcp)
                    self.assertEqual(mcp.status, "BLOCKED" if tampered else "READY_FOR_REVIEW")
                    if not tampered:
                        self.assertEqual(mcp.native_status, "FAIL")
                        self.assertEqual(mcp.review_state, "UNREVIEWED")
                    self.assertFalse(mcp.electrical_coverage)

    async def test_model_coverage_parity(self) -> None:
        board = self.island / "kicad/controller.kicad_pcb"
        async with Client(create_server(self.root), mode="legacy") as client:
            for broken in (False, True):
                with self.subTest(missing_assigned_model=broken):
                    assignment = '(model "${KIPRJMOD}/missing.step")' if broken else ""
                    board.write_text(
                        '(kicad_pcb (footprint "Test:Part" '
                        f'(property "Reference" "U1") {assignment}))',
                        encoding="utf-8",
                    )
                    cli = await self.cli(
                        "kicad_tooling.visualize",
                        ThreeDReport,
                        "--project",
                        "controller",
                        "--check-models",
                        expected_exit=int(broken),
                    )
                    mcp = await self.call(
                        client,
                        "inspect_3d_models",
                        ModelInventoryReport,
                        {"project_id": "controller"},
                    )
                    self.assertEqual(cli.models, mcp)
                    self.assertEqual(mcp.status, "FAIL" if broken else "REVIEW")
                    self.assertEqual(cli.mode, "inspect")
                    self.assertEqual(cli.runner, "none")

    async def test_parts_preferences_parity(self) -> None:
        path = self.island / "docs/purchasing.json"
        cli = await self.cli(
            "kicad_tooling.parts",
            PurchasingPreferences,
            "--project",
            "controller",
            "--init-preferences",
            str(path),
            "--boards",
            "10",
            "--spare-percent",
            "10",
            "--spare-minimum",
            "3",
        )
        expected_bytes = path.read_bytes()
        path.unlink()
        async with Client(create_server(self.root, allow_edits=True), mode="legacy") as client:
            mcp = await self.call(
                client,
                "save_parts_preferences",
                McpPurchasingPreferencesResult,
                {
                    "project_id": "controller",
                    "preferences": cli.model_dump(mode="json"),
                },
            )
        self.assertEqual(cli, mcp.preferences)
        self.assertEqual(path.read_bytes(), expected_bytes)
        self.assertEqual(mcp.after_sha256, digest(path))
        self.assertEqual(mcp.readback_sha256, mcp.after_sha256)
        self.assertFalse(mcp.purchase_authorized)

        # Compare the shared explicit save/update operation, including stale writes.
        path.unlink()
        cli_created = await self.cli(
            "kicad_tooling.parts",
            McpPurchasingPreferencesResult,
            "--project",
            "controller",
            "--save-preferences",
            "--boards",
            "10",
            "--spare-percent",
            "10",
            "--spare-minimum",
            "3",
        )
        original = path.read_bytes()
        path.unlink()
        async with Client(create_server(self.root, allow_edits=True), mode="legacy") as client:
            created = await self.call(
                client,
                "save_parts_preferences",
                McpPurchasingPreferencesResult,
                {
                    "project_id": "controller",
                    "preferences": cli_created.preferences.model_dump(mode="json"),
                },
            )
            self.assertEqual(cli_created, created)
            self.assertEqual(path.read_bytes(), original)
            cli_updated = await self.cli(
                "kicad_tooling.parts",
                McpPurchasingPreferencesResult,
                "--project",
                "controller",
                "--save-preferences",
                "--boards",
                "20",
                "--expected-sha256",
                created.after_sha256,
            )
            updated_bytes = path.read_bytes()
            path.write_bytes(original)
            updated = await self.call(
                client,
                "save_parts_preferences",
                McpPurchasingPreferencesResult,
                {
                    "project_id": "controller",
                    "preferences": cli_updated.preferences.model_dump(mode="json"),
                    "expected_sha256": created.after_sha256,
                },
            )
            self.assertEqual(cli_updated, updated)
            self.assertEqual(path.read_bytes(), updated_bytes)
            rejected_cli = await self.cli_process(
                "kicad_tooling.parts",
                "--project",
                "controller",
                "--save-preferences",
                "--boards",
                "30",
                "--expected-sha256",
                created.after_sha256,
            )
            self.assertEqual(rejected_cli.returncode, 2)
            rejected_mcp = await client.call_tool(
                "save_parts_preferences",
                {
                    "project_id": "controller",
                    "preferences": {"boards": 30},
                    "expected_sha256": created.after_sha256,
                },
            )
            self.assertTrue(rejected_mcp.is_error)
            self.assertIn("Source hash mismatch", rejected_cli.stderr)
            self.assertIn("Source hash mismatch", str(rejected_mcp.content))
            self.assertEqual(path.read_bytes(), updated_bytes)

    async def test_parts_quantities_and_native_failure_parity(self) -> None:
        native = self.native_evidence()
        write_model(
            self.island / "docs/purchasing.json",
            PurchasingPreferences(
                boards=4,
                spare_percent=10,
                spare_minimum=3,
            ),
        )
        cli = await self.cli(
            "kicad_tooling.parts",
            PurchasingReport,
            "--project",
            "controller",
            "--native-summary",
            str(native),
            "--boards",
            "10",
            "--output",
            str(self.root / "build/parts/cli-quantities"),
        )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client,
                "prepare_parts",
                PurchasingReport,
                {
                    "project_id": "controller",
                    "view_id": "mcp-quantities",
                    "boards": 10,
                    "native_summary": native.relative_to(self.root).as_posix(),
                },
            )
        self.receipt_equal(cli, mcp, "receipt_dir")
        self.assertIsNotNone(mcp.plan)
        self.assertEqual(mcp.plan.lines[0].quantity, 23)
        self.assertEqual(mcp.plan.excluded_references, ("C1",))
        self.assertEqual(mcp.native_status, "FAIL")
        self.assertEqual(mcp.status, "READY_FOR_ORDER_REVIEW")
        self.assertFalse(mcp.purchase_authorized)
        self.assertFalse(mcp.build_authorized)
        for name in ("bom.csv", "digikey.csv", "netlist.xml"):
            self.assertEqual(
                (Path(cli.receipt_dir) / name).read_bytes(),
                (Path(mcp.receipt_dir) / name).read_bytes(),
            )

    async def test_parts_stale_evidence_parity(self) -> None:
        native = self.native_evidence()
        schematic = self.island / "kicad/controller.kicad_sch"
        schematic.write_text(schematic.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        cli = await self.cli(
            "kicad_tooling.parts",
            PurchasingReport,
            "--project",
            "controller",
            "--native-summary",
            str(native),
            "--output",
            str(self.root / "build/parts/cli-stale"),
            expected_exit=1,
        )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client,
                "prepare_parts",
                PurchasingReport,
                {
                    "project_id": "controller",
                    "view_id": "mcp-stale",
                    "native_summary": native.relative_to(self.root).as_posix(),
                },
            )
        self.receipt_equal(cli, mcp, "receipt_dir")
        self.assertEqual(mcp.status, "BLOCKED")
        self.assertIsNone(mcp.plan)
        self.assertTrue(mcp.issues)
        self.assertFalse((Path(mcp.receipt_dir) / "digikey.csv").exists())


if __name__ == "__main__":
    unittest.main()
