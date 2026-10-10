"""Project import CLI/MCP parity cases."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.parity_lint, pytest.mark.slow, pytest.mark.template_checkout]

import shutil

from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DiagnosticReport,
    ImportInventoryReport,
    ProjectImportReport,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)


class _McpParityImportsCases(McpParityHarness):
    async def _case_test_import_preview_parity(self) -> None:
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

    async def _case_test_import_scan_parity(self) -> None:
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

    async def _case_test_import_diagnosis_parity(self) -> None:
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

    async def _case_test_import_write_parity(self) -> None:
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


def test_import_preview_parity() -> None:
    run_mcp_parity(_McpParityImportsCases, "_case_test_import_preview_parity")


def test_import_scan_parity() -> None:
    run_mcp_parity(_McpParityImportsCases, "_case_test_import_scan_parity")


def test_import_diagnosis_parity() -> None:
    run_mcp_parity(_McpParityImportsCases, "_case_test_import_diagnosis_parity")


def test_import_write_parity() -> None:
    run_mcp_parity(_McpParityImportsCases, "_case_test_import_write_parity")
