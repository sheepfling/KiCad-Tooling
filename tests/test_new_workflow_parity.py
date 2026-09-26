"""CLI/MCP parity for new chart exports and exact sourced CAD workflows."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    CadImportReport,
    CadSourceReport,
    CadSourcingReview,
    CadStepReport,
    ElectricalChartsReport,
    ElectricalChartsSuiteReport,
    ElectricalSuiteReport,
)
from kicad_tooling.parts import main as parts_main
from tests import test_cad_library as cad_fixture
from tests import test_electrical_charts as chart_fixture
from tests.support import SOURCE_ROOT


class NewWorkflowParityTests(unittest.IsolatedAsyncioTestCase):
    def cad_fixture(self) -> tuple[cad_fixture.CadLibraryTests, CadSourceReport]:
        fixture = cad_fixture.CadLibraryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        cache = fixture.root / "build/cad-source-cache/easyeda-1.0.1/C1234" / ("a" * 64) / "bundle"
        cache.parent.mkdir(parents=True)
        shutil.copytree(fixture.bundle_dir, cache)
        source = CadSourceReport(
            status="READY",
            supplier_id="C1234",
            bundle_directory=str(cache),
            bundle=fixture.bundle,
            receipt_directory=str(fixture.root / "build/cad-source/saved"),
        )
        return fixture, source

    @staticmethod
    def cli_parts(root: Path, *args: str) -> tuple[int, dict[str, object]]:
        output = StringIO()
        with (
            patch.object(
                sys,
                "argv",
                [
                    "kicad_tooling.parts",
                    "--root",
                    str(root),
                    "--project",
                    "controller",
                    *args,
                    "--format",
                    "json",
                ],
            ),
            redirect_stdout(output),
        ):
            status = parts_main()
        return status, json.loads(output.getvalue())

    @staticmethod
    def project_bytes(root: Path) -> dict[str, bytes]:
        base = root / "examples/projects/controller"
        return {
            path.relative_to(base).as_posix(): path.read_bytes()
            for path in base.rglob("*")
            if path.is_file() and "build" not in path.parts
        }

    async def test_saved_electrical_charts_and_suite_match_cli(self) -> None:
        fixture = chart_fixture.ElectricalChartsTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        analysis = fixture.complete()
        root = fixture.root
        source = Path(analysis.run_directory).relative_to(root).as_posix()
        process = await asyncio.to_thread(
            subprocess.run,
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.electrical_charts",
                "--root",
                str(root),
                "--receipt",
                source,
                "--output",
                "build/electrical-charts/cli",
                "--format",
                "json",
            ),
            cwd=SOURCE_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=90,
            env={**os.environ, "MPLCONFIGDIR": str(root / "build/matplotlib")},
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        cli = ElectricalChartsReport.model_validate_json(process.stdout)
        async with Client(create_server(root, allow_exports=True), mode="legacy") as client:
            response = await client.call_tool(
                "export_electrical_charts", {"receipt": source, "view_id": "mcp"}
            )
            self.assertFalse(response.is_error, response.content)
            mcp = ElectricalChartsReport.model_validate_json(
                json.dumps(response.structured_content)
            )
            self.assertEqual(
                [
                    (
                        item.id,
                        item.status,
                        item.samples,
                        item.waveform_sha256,
                        item.csv,
                        item.png,
                        item.svg,
                    )
                    for item in cli.cases
                ],
                [
                    (
                        item.id,
                        item.status,
                        item.samples,
                        item.waveform_sha256,
                        item.csv,
                        item.png,
                        item.svg,
                    )
                    for item in mcp.cases
                ],
            )
            self.assertEqual(cli.source_report_sha256, mcp.source_report_sha256)
            self.assertEqual(cli.status, mcp.status)
            for case in cli.cases:
                assert case.csv is not None
                self.assertEqual(
                    (Path(cli.run_directory) / case.csv).read_bytes(),
                    (Path(mcp.run_directory) / case.csv).read_bytes(),
                )
            suite_path = root / "build/electrical-suite.json"
            write_model(suite_path, ElectricalSuiteReport(status="PASS", projects=(analysis,)))
            process = await asyncio.to_thread(
                subprocess.run,
                (
                    sys.executable,
                    "-I",
                    "-B",
                    "-m",
                    "kicad_tooling.electrical_charts",
                    "--root",
                    str(root),
                    "--suite",
                    "build/electrical-suite.json",
                    "--output",
                    "build/electrical-charts/cli-suite",
                    "--format",
                    "json",
                ),
                cwd=SOURCE_ROOT,
                text=True,
                capture_output=True,
                check=False,
                timeout=90,
                env={**os.environ, "MPLCONFIGDIR": str(root / "build/matplotlib")},
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            cli_suite = ElectricalChartsSuiteReport.model_validate_json(process.stdout)
            response = await client.call_tool(
                "export_electrical_chart_suite",
                {"suite": "build/electrical-suite.json", "view_id": "mcp-suite"},
            )
            self.assertFalse(response.is_error, response.content)
            mcp_suite = ElectricalChartsSuiteReport.model_validate_json(
                json.dumps(response.structured_content)
            )
            self.assertEqual(cli_suite.status, mcp_suite.status)
            self.assertEqual(
                [(item.project_id, item.status) for item in cli_suite.reports],
                [(item.project_id, item.status) for item in mcp_suite.reports],
            )
            outside = await client.call_tool(
                "export_electrical_charts",
                {"receipt": "docs/workflow/ELECTRICAL_ANALYSIS.md", "view_id": "outside"},
            )
            self.assertTrue(outside.is_error)

    async def test_exact_cad_lookup_preview_and_apply_match_cli(self) -> None:
        cli_fixture, cli_source = self.cad_fixture()
        mcp_fixture, mcp_source = self.cad_fixture()
        with patch("kicad_tooling.hwrepo.cad_source.fetch", return_value=cli_source):
            status, value = self.cli_parts(cli_fixture.root, "--source-cad", "C1234")
        self.assertEqual(status, 0)
        cli_review = CadSourcingReview.model_validate_json(json.dumps(value))
        async with Client(
            create_server(mcp_fixture.root, allow_exports=True, allow_edits=True), mode="legacy"
        ) as client:
            with patch("kicad_tooling.hwrepo.cad_source.fetch", return_value=mcp_source) as fetch:
                result = await client.call_tool(
                    "source_cad",
                    {"project_id": "controller", "view_id": "source", "supplier_id": "C1234"},
                )
            self.assertFalse(result.is_error, result.content)
            self.assertFalse(fetch.call_args.kwargs["allow_downloads"])
            mcp_review = CadSourcingReview.model_validate_json(
                json.dumps(result.structured_content)
            )
            assert cli_review.import_plan is not None and mcp_review.import_plan is not None
            cli_plan, mcp_plan = cli_review.import_plan, mcp_review.import_plan
            self.assertEqual(
                (
                    cli_plan.status,
                    cli_plan.symbol_id,
                    cli_plan.footprint_id,
                    cli_plan.files,
                    cli_plan.check,
                    cli_plan.diff,
                ),
                (
                    mcp_plan.status,
                    mcp_plan.symbol_id,
                    mcp_plan.footprint_id,
                    mcp_plan.files,
                    mcp_plan.check,
                    mcp_plan.diff,
                ),
            )
            self.assertEqual(cli_plan.status, "PLAN")
            assert cli_plan.plan_path is not None and mcp_plan.plan_path is not None
            cli_status, cli_value = self.cli_parts(
                cli_fixture.root, "--import-cad", cli_plan.plan_path, "--apply"
            )
            self.assertEqual(cli_status, 0)
            cli_applied = CadImportReport.model_validate_json(json.dumps(cli_value))
            mcp_plan_relative = Path(mcp_plan.plan_path).relative_to(mcp_fixture.root).as_posix()
            expected = hashlib.sha256(Path(mcp_plan.plan_path).read_bytes()).hexdigest()
            result = await client.call_tool(
                "apply_cad_import",
                {
                    "project_id": "controller",
                    "view_id": "apply",
                    "plan": mcp_plan_relative,
                    "expected_sha256": expected,
                },
            )
            self.assertFalse(result.is_error, result.content)
            mcp_applied = CadImportReport.model_validate_json(json.dumps(result.structured_content))
            self.assertEqual(
                (
                    cli_applied.status,
                    cli_applied.files,
                    cli_applied.symbol_id,
                    cli_applied.footprint_id,
                ),
                (
                    mcp_applied.status,
                    mcp_applied.files,
                    mcp_applied.symbol_id,
                    mcp_applied.footprint_id,
                ),
            )
            self.assertEqual(cli_applied.status, "APPLIED")
            self.assertEqual(
                self.project_bytes(cli_fixture.root), self.project_bytes(mcp_fixture.root)
            )
            replay = await client.call_tool(
                "apply_cad_import",
                {
                    "project_id": "controller",
                    "view_id": "replay",
                    "plan": mcp_plan_relative,
                    "expected_sha256": expected,
                },
            )
            self.assertFalse(replay.is_error, replay.content)
            self.assertEqual(
                CadImportReport.model_validate_json(json.dumps(replay.structured_content)).status,
                "BLOCKED",
            )

    async def test_network_permission_and_step_review_match_cli(self) -> None:
        fixture, source = self.cad_fixture()
        root = fixture.root
        async with Client(
            create_server(root, allow_exports=True, allow_checks=True), mode="legacy"
        ) as client:
            with patch(
                "kicad_tooling.hwrepo.cad_source._download", side_effect=AssertionError("network")
            ):
                result = await client.call_tool(
                    "source_cad",
                    {"project_id": "controller", "view_id": "offline", "supplier_id": "C9999"},
                )
            self.assertFalse(result.is_error, result.content)
            self.assertEqual(
                CadSourcingReview.model_validate_json(
                    json.dumps(result.structured_content)
                ).source.status,
                "BLOCKED",
            )
            self.assertFalse(
                (root / "build/cad-source-cache/easyeda-1.0.1/C9999/current.txt").exists()
            )
            review = CadStepReport(
                status="REVIEW",
                project_id="controller",
                supplier_id="C1234",
                receipt_directory="synthetic",
                issues=("Inspect paired views",),
            )
            with (
                patch("kicad_tooling.hwrepo.cad_source.fetch", return_value=source),
                patch("kicad_tooling.hwrepo.cad_step.review", return_value=review),
            ):
                cli_status, cli_value = self.cli_parts(root, "--check-step", "C1234")
                response = await client.call_tool(
                    "check_step_alignment",
                    {"project_id": "controller", "view_id": "step", "supplier_id": "C1234"},
                )
            self.assertEqual(cli_status, 0)
            self.assertFalse(response.is_error, response.content)
            self.assertEqual(
                CadStepReport.model_validate_json(json.dumps(cli_value)),
                CadStepReport.model_validate_json(json.dumps(response.structured_content)),
            )
            self.assertFalse(review.alignment_verified)


if __name__ == "__main__":
    unittest.main()
