"""Real CLI/MCP source-edit parity and fresh capture using an external synthetic CLI."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import ContractCoachReport, ModelMap, ModelPopulationReport
from kicad_tooling.validate import hashes
from tests import test_model_population as population_fixture
from tests.support import SOURCE_ROOT
from tests.test_contract_coach import NETLIST, fake_executable


def source_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()
            and not {".git", "build", "__pycache__"}.intersection(path.relative_to(root).parts)}


class SourceParityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.fixture = population_fixture.ModelPopulationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.mcp_root = self.root.parent / "mcp-repository"
        shutil.copytree(self.root, self.mcp_root)

    async def cli(self, module: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return await asyncio.to_thread(
            subprocess.run,
            (sys.executable, "-B", "-m", module, "--root", str(self.root),
             *arguments, "--format", "json"),
            cwd=self.root.parent, env={**os.environ, "PYTHONPATH": str(SOURCE_ROOT)},
            text=True, capture_output=True, check=False, timeout=60,
        )

    async def test_model_population_preview_apply_parity(self) -> None:
        original = source_bytes(self.root)
        self.assertEqual(source_bytes(self.mcp_root), original)
        spec = read_model(self.fixture.map, ModelMap)
        preview = await self.cli(
            "kicad_tooling.visualize", "--project", population_fixture.PROJECT,
            "--map-models", "build/model-map.json", "--output", "build/cli-plan",
        )
        self.assertEqual(preview.returncode, 0, preview.stderr + preview.stdout)
        cli_plan = ModelPopulationReport.model_validate_json(preview.stdout)
        async with Client(create_server(self.mcp_root, allow_edits=True), mode="legacy") as client:
            preview_result = await client.call_tool("preview_model_population", {
                "project_id": population_fixture.PROJECT, "board_sha256": spec.board_sha256,
                "assignments": [assignment.model_dump(mode="json") for assignment in spec.assignments],
            })
            self.assertFalse(preview_result.is_error, preview_result.content)
            mcp_plan = ModelPopulationReport.model_validate_json(json.dumps(preview_result.structured_content))
            for report in (cli_plan, mcp_plan):
                self.assertEqual(report.status, "PLAN", report.error)
                self.assertEqual(report.board_sha256, spec.board_sha256)
                self.assertEqual(report.manifest_sha256, spec.manifest_sha256)
                self.assertEqual(report.model_sha256[population_fixture.MODEL],
                                 hashlib.sha256(self.fixture.model.read_bytes()).hexdigest())
                self.assertFalse(report.build_authorized)
                self.assertTrue(report.checks_required)
            self.assertEqual(cli_plan.board_diff, mcp_plan.board_diff)
            self.assertEqual(cli_plan.manifest_diff, mcp_plan.manifest_diff)
            self.assertEqual(source_bytes(self.root), original)
            self.assertEqual(source_bytes(self.mcp_root), original)
            self.assertIsNotNone(cli_plan.locked_map)
            applied = await self.cli(
                "kicad_tooling.visualize", "--project", population_fixture.PROJECT,
                "--map-models", str(cli_plan.locked_map), "--apply", "--output", "build/cli-apply",
            )
            self.assertEqual(applied.returncode, 0, applied.stderr + applied.stdout)
            cli_apply = ModelPopulationReport.model_validate_json(applied.stdout)
            plan = (Path(mcp_plan.run_directory) / "model-population.json").relative_to(self.mcp_root)
            applied_result = await client.call_tool("apply_model_population", {
                "project_id": population_fixture.PROJECT, "plan": plan.as_posix(),
            })
            self.assertFalse(applied_result.is_error, applied_result.content)
            mcp_apply = ModelPopulationReport.model_validate_json(json.dumps(applied_result.structured_content))
        for report in (cli_apply, mcp_apply):
            self.assertEqual(report.status, "APPLIED", report.error)
            self.assertFalse(report.build_authorized)
            self.assertTrue(report.checks_required)
            self.assertEqual(report.board_diff, cli_plan.board_diff)
            self.assertEqual(report.manifest_diff, cli_plan.manifest_diff)
            self.assertEqual(report.model_sha256, cli_plan.model_sha256)
        after = source_bytes(self.root)
        self.assertEqual(source_bytes(self.mcp_root), after)
        changed = {name for name in original if original[name] != after[name]}
        self.assertEqual(changed, {population_fixture.BOARD, population_fixture.MANIFEST})
        self.assertIn(b'${KIPRJMOD}/models/Header_1x02.step', after[population_fixture.BOARD])

    async def test_model_population_assignment_schema_rejects_malformed_inputs(self) -> None:
        before = source_bytes(self.mcp_root)
        spec = read_model(self.fixture.map, ModelMap)
        assignment = {"reference": "J1", "model": population_fixture.MODEL}
        invalid = (
            {"candidate_assets": [1]}, {"candidate_assets": [True]},
            {"candidate_assets": [None]}, {"candidate_assets": [""]},
            {"candidate_assets": [[population_fixture.MODEL]]},
            {"candidate_assets": population_fixture.MODEL},
            {"candidate_assets": [], "unexpected": "not part of the contract"},
        )
        async with Client(create_server(self.mcp_root, allow_edits=True), mode="legacy") as client:
            for update in invalid:
                with self.subTest(update=update):
                    result = await client.call_tool("preview_model_population", {
                        "project_id": population_fixture.PROJECT,
                        "board_sha256": spec.board_sha256,
                        "assignments": [assignment | update],
                    })
                    self.assertTrue(result.is_error, result.content)
                    self.assertEqual(source_bytes(self.mcp_root), before)
                    self.assertFalse((self.mcp_root / "build/diagnostics").exists())

    async def test_contract_capture_parity(self) -> None:
        project_id = "controller"
        config = load_config(self.root, f"examples/projects/{project_id}/project.json")
        before = source_bytes(self.root)
        expected_hashes = hashes(self.root, config.source_roots)
        binary = self.root.parent / "external-bin"
        binary.mkdir()
        executable = fake_executable(binary / "kicad-cli", (
            "from pathlib import Path\nimport sys\n"
            "if sys.argv[1:] == ['version']:\n"
            f"    print({config.kicad_version!r})\n"
            "elif sys.argv[1:4] == ['sch', 'export', 'netlist']:\n"
            f"    Path(sys.argv[sys.argv.index('--output') + 1]).write_text({NETLIST!r}, encoding='utf-8')\n"
            "    print('Synthetic native export progress')\n"
            "else:\n    raise SystemExit(2)\n"
        ))
        self.assertFalse(executable.is_relative_to(self.root))
        self.assertFalse(executable.is_relative_to(self.mcp_root))
        with patch.dict(os.environ, {"PATH": str(binary) + os.pathsep + os.environ.get("PATH", "")}):
            process = await self.cli(
                "kicad_tooling.contract_coach", "--project-id", project_id,
                "--capture", "--runner", "local", "--output", "build/cli-contract",
            )
            self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
            cli_report = ContractCoachReport.model_validate_json(process.stdout)
            async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
                result = await client.call_tool("capture_contract", {
                    "project_id": project_id, "runner": "local",
                })
            self.assertFalse(result.is_error, result.content)
            mcp_report = ContractCoachReport.model_validate_json(json.dumps(result.structured_content))
        self.assertEqual(cli_report.observed, mcp_report.observed)
        self.assertEqual(cli_report.authored, mcp_report.authored)
        self.assertEqual(cli_report.differences, mcp_report.differences)
        self.assertEqual(cli_report.netlist_sha256, mcp_report.netlist_sha256)
        for report in (cli_report, mcp_report):
            self.assertEqual(report.status, "READY_FOR_REVIEW", report.issues)
            self.assertEqual(report.source_hashes, expected_hashes)
            self.assertEqual(report.selected_runner, "local")
            self.assertEqual(report.review_state, "UNREVIEWED")
            self.assertFalse(report.electrical_coverage)
            self.assertFalse(report.build_authorized)
            self.assertIsNone(report.native_status)
            self.assertEqual(report.commands["version"].stdout.strip(), config.kicad_version)
            self.assertEqual(report.commands["netlist"].returncode, 0)
            self.assertIn("Synthetic native export progress", report.commands["netlist"].stdout)
            receipt = Path(report.receipt_dir)
            self.assertEqual((receipt / "netlist.xml").read_text(encoding="utf-8"), NETLIST)
            self.assertEqual(read_model(receipt / "report.json", ContractCoachReport), report)
        self.assertEqual(source_bytes(self.root), before)
        self.assertEqual(source_bytes(self.mcp_root), before)


if __name__ == "__main__":
    unittest.main()
