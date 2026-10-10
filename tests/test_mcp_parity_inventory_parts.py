"""Project workflow CLI/MCP parity cases: mcp parity inventory parts."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.parity_lint, pytest.mark.slow, pytest.mark.template_checkout]

import os
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    McpPurchasingPreferencesResult,
    ModelInventoryReport,
    PurchasingPreferences,
    PurchasingReport,
    TemplateDoctorReport,
    TemplateInventoryReport,
    ThreeDReport,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)


class _McpParityInventoryPartsCases(McpParityHarness):
    async def _case_test_inventory_parity(self) -> None:
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

    async def _case_test_doctor_failure_parity(self) -> None:
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

    async def _case_test_model_coverage_parity(self) -> None:
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

    async def _case_test_parts_preferences_parity(self) -> None:
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

    async def _case_test_parts_quantities_and_native_failure_parity(self) -> None:
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

    async def _case_test_parts_stale_evidence_parity(self) -> None:
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


def test_inventory_parity() -> None:
    run_mcp_parity(_McpParityInventoryPartsCases, "_case_test_inventory_parity")


def test_doctor_failure_parity() -> None:
    run_mcp_parity(_McpParityInventoryPartsCases, "_case_test_doctor_failure_parity")


def test_model_coverage_parity() -> None:
    run_mcp_parity(_McpParityInventoryPartsCases, "_case_test_model_coverage_parity")


def test_parts_preferences_parity() -> None:
    run_mcp_parity(_McpParityInventoryPartsCases, "_case_test_parts_preferences_parity")


def test_parts_quantities_and_native_failure_parity() -> None:
    run_mcp_parity(
        _McpParityInventoryPartsCases, "_case_test_parts_quantities_and_native_failure_parity"
    )


def test_parts_stale_evidence_parity() -> None:
    run_mcp_parity(_McpParityInventoryPartsCases, "_case_test_parts_stale_evidence_parity")
