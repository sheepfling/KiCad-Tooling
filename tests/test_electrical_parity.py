"""CLI/protocol electrical parity, source authority and bounded input regressions."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from kicad_tooling.hwrepo import electrical_setup, mcp_electrical, mcp_files
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.electrical import regular_input_bytes, simulation_cases
from kicad_tooling.hwrepo.electrical_runner import analyze
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    ElectricalInputInventory,
    ElectricalSetupReport,
    ElectricalSuiteReport,
    GroundDomain,
    GroundingAnalysis,
    ProjectVerificationReport,
    TemplateDoctorReport,
)
from kicad_tooling.hwrepo.spice import expanded_deck
from tests import test_contract_coach as coach_fixture
from tests.support import initialize_git
from tests.test_contract_coach import fake_executable
from tests.test_electrical import ISLAND, NA, PROJECT, install_fixture
from tests.test_source_parity import source_bytes


class ElectricalParityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.fixture = coach_fixture.ContractCoachTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.mcp_root = self.root.parent / "mcp-repository"
        shutil.copytree(self.root, self.mcp_root)

    async def cli(self, module: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return await asyncio.to_thread(
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
            cwd=self.root.parent,
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )

    def configured(self, *, simulation: bool = False, grounding: bool = False) -> None:
        for root in (self.root, self.mcp_root):
            contract = install_fixture(root)
            contract = contract.model_copy(
                update={
                    "grounding": GroundingAnalysis(
                        basis="Synthetic independently authored pin review",
                        domains=(GroundDomain(net="PILOT_C", pins=("R1.2", "R3.2")),),
                    )
                    if grounding
                    else NA,
                    "high_frequency": NA,
                    **({} if simulation else {"power": NA}),
                }
            )
            write_model(root / ISLAND / "tests/electrical.json", contract)

    async def test_init_and_capture_match_cli_without_approving_requirements(self) -> None:
        before = source_bytes(self.root)
        process = await self.cli("kicad_tooling.electrical", "--project", PROJECT, "--init")
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_setup = ElectricalSetupReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_edits=True), mode="legacy") as client:
            result = await client.call_tool("init_electrical", {"project_id": PROJECT})
            self.assertFalse(result.is_error, result.content)
            mcp_setup = ElectricalSetupReport.model_validate_json(
                json.dumps(result.structured_content)
            )
            again = await client.call_tool("init_electrical", {"project_id": PROJECT})
            self.assertTrue(again.is_error)
        self.assertEqual(cli_setup, mcp_setup)
        self.assertFalse(mcp_setup.build_authorized)
        self.assertEqual(source_bytes(self.root), source_bytes(self.mcp_root))
        after = source_bytes(self.root)
        self.assertEqual(
            {name for name in before if before[name] != after[name]},
            {f"{ISLAND}/tests/contract.json"},
        )
        self.assertEqual(set(after) - set(before), {f"{ISLAND}/tests/electrical.json"})
        contract = read_model(self.root / cli_setup.contract, ElectricalAnalysisContract)
        self.assertEqual(
            [contract.grounding.mode, contract.power.mode, contract.high_frequency.mode],
            ["pending"] * 3,
        )
        name = f"{ISLAND}/tests/draft.cir"
        for root in (self.root, self.mcp_root):
            (root / name).write_text(
                "Synthetic unreviewed model\nR1 in 0 1k\n.end\n", encoding="utf-8"
            )
        before = source_bytes(self.root)
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--capture-inputs",
            "--model",
            name,
            "--output",
            "build/electrical-inputs/parity",
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_capture = ElectricalInputInventory.model_validate_json(process.stdout)
        async with Client(
            create_server(self.mcp_root, allow_exports=True), mode="legacy"
        ) as client:
            result = await client.call_tool(
                "capture_electrical_inputs",
                {
                    "project_id": PROJECT,
                    "view_id": "parity",
                    "models": [name],
                },
            )
            self.assertFalse(result.is_error, result.content)
            mcp_capture = ElectricalInputInventory.model_validate_json(
                json.dumps(result.structured_content)
            )
            collision = await client.call_tool(
                "capture_electrical_inputs",
                {
                    "project_id": PROJECT,
                    "view_id": "parity",
                    "models": [name],
                },
            )
            self.assertTrue(collision.is_error)
        self.assertEqual(
            cli_capture.model_copy(update={"run_directory": ""}),
            mcp_capture.model_copy(update={"run_directory": ""}),
        )
        self.assertEqual(mcp_capture.status, "UNREVIEWED")
        self.assertFalse(mcp_capture.build_authorized)
        self.assertEqual(mcp_capture.model_sha256, {name: digest(self.root / name)})
        self.assertEqual(source_bytes(self.root), before)
        self.assertEqual(source_bytes(self.mcp_root), before)

    async def test_saved_native_analysis_is_root_relative_and_preserves_native_failure(
        self,
    ) -> None:
        self.configured(grounding=True)
        before = source_bytes(self.root)
        summary = "build/native/controller/summary.json"
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary,
            "--output",
            "build/electrical/saved",
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "saved",
                    "native_summary": summary,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_report.checks, mcp_report.checks)
        self.assertEqual(cli_report.input_sha256, mcp_report.input_sha256)
        for report in (cli_report, mcp_report):
            self.assertEqual(report.status, "PASS")
            self.assertFalse(report.build_authorized)
            self.assertEqual(report.commands, {})
            evidence = read_model(
                Path(report.run_directory) / "netlist-evidence.json", ContractCoachReport
            )
            self.assertEqual(evidence.native_status, "FAIL")
            self.assertEqual(evidence.review_state, "UNREVIEWED")
            self.assertFalse(evidence.build_authorized)
        self.assertEqual(source_bytes(self.root), before)
        self.assertEqual(source_bytes(self.mcp_root), before)

    async def test_external_fixed_simulator_success_and_wrong_version_match_cli(self) -> None:
        self.configured(simulation=True)
        before = source_bytes(self.root)
        binary = self.root.parent / "external-bin"
        binary.mkdir()
        waveform = (
            "Title: synthetic\nFlags: real\nNo. Variables: 2\nNo. Points: 4\n"
            "Variables:\n0 time time\n1 v(out) voltage\nValues:\n"
            "0 0\n0\n1 0.001\n4.9\n2 0.004\n4.95\n3 0.005\n5\n"
        )
        executable = fake_executable(
            binary / "ngspice",
            (
                "from pathlib import Path\nimport sys\n"
                "if sys.argv[1:] == ['--version']:\n    print('ngspice-47')\n"
                "else:\n"
                f"    Path('waveforms.raw').write_text({waveform!r})\n"
                "    print('Synthetic simulator progress')\n"
                "    print('check0 = 4.95' if Path.cwd().name == 'startup' else "
                "'check0 = 0.05\\ncheck1 = 0.25\\ncheck2 = 4.95')\n"
            ),
        )
        self.assertFalse(executable.is_relative_to(self.root))
        with patch.dict(
            os.environ, {"PATH": str(binary) + os.pathsep + os.environ.get("PATH", "")}
        ):
            async with Client(
                create_server(self.mcp_root, allow_checks=True), mode="legacy"
            ) as client:
                for view, version, status in (
                    ("simulation", "47", "PASS"),
                    ("wrong-version", "46", "FAIL"),
                ):
                    if version == "46":
                        fake_executable(binary / "ngspice", "print('ngspice-46')\n")
                    process = await self.cli(
                        "kicad_tooling.electrical",
                        "--project",
                        PROJECT,
                        "--output",
                        f"build/electrical/{view}",
                    )
                    self.assertEqual(
                        process.returncode,
                        0 if status == "PASS" else 1,
                        process.stderr + process.stdout,
                    )
                    cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
                    result = await client.call_tool(
                        "analyze_electrical", {"project_id": PROJECT, "view_id": view}
                    )
                    self.assertFalse(result.is_error, result.content)
                    mcp_report = ElectricalAnalysisReport.model_validate_json(
                        json.dumps(result.structured_content)
                    )
                    self.assertEqual(cli_report.checks, mcp_report.checks)
                    self.assertEqual(cli_report.input_sha256, mcp_report.input_sha256)
                    for report in (cli_report, mcp_report):
                        self.assertEqual(report.status, status)
                        self.assertFalse(report.build_authorized)
                        if status == "PASS":
                            self.assertIn(
                                "Synthetic simulator progress", report.commands["startup"].stdout
                            )
                            self.assertEqual(
                                set(report.commands), {"version", "startup", "steady-state"}
                            )
                        else:
                            self.assertTrue(any(row.status == "NOT_RUN" for row in report.checks))
                            self.assertTrue(
                                (
                                    Path(report.run_directory) / "ngspice-version.command.json"
                                ).is_file()
                            )
        self.assertEqual(source_bytes(self.root), before)
        self.assertEqual(source_bytes(self.mcp_root), before)

    async def test_scope_selection_preserves_mixed_outcomes_like_ci(self) -> None:
        self.configured()
        process = await self.cli(
            "kicad_tooling.ci", "--electrical", "--tag", "training", "--project", PROJECT
        )
        self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
        cli_report = ElectricalSuiteReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "check_electrical_scope", {"tags": ["training"], "project_ids": [PROJECT]}
            )
            self.assertFalse(result.is_error, result.content)
            mcp_report = ElectricalSuiteReport.model_validate_json(
                json.dumps(result.structured_content)
            )
            invalid = await client.call_tool(
                "check_electrical_scope", {"project_ids": ["missing-project"]}
            )
            self.assertTrue(invalid.is_error)
        self.assertEqual(
            [(row.project_id, row.status, row.checks) for row in cli_report.projects],
            [(row.project_id, row.status, row.checks) for row in mcp_report.projects],
        )
        self.assertFalse(mcp_report.build_authorized)
        self.assertEqual(mcp_report.status, "FAIL")
        self.assertEqual({row.status for row in mcp_report.projects}, {"PASS", "NOT_CONFIGURED"})

    async def test_doctor_and_verification_electrical_preflight_match_cli(self) -> None:
        self.configured(simulation=True)
        for root in (self.root, self.mcp_root):
            initialize_git(root)
        binary = self.root.parent / "electrical-preflight-bin"
        binary.mkdir()
        fake_executable(binary / "ngspice", "print('ngspice-46')\n")
        fake_executable(binary / "kicad-cli", f"print({self.fixture.config.kicad_version!r})\n")
        with patch.dict(
            os.environ, {"PATH": str(binary) + os.pathsep + os.environ.get("PATH", "")}
        ):
            process = await self.cli(
                "kicad_tooling.template",
                "doctor",
                "--electrical",
                "--project-id",
                PROJECT,
                "--runner",
                "local",
            )
            self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
            cli_doctor = TemplateDoctorReport.model_validate_json(process.stdout)
            process = await self.cli(
                "kicad_tooling.verify",
                "--project",
                PROJECT,
                "--depth",
                "electrical",
                "--runner",
                "local",
            )
            self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
            cli_check = ProjectVerificationReport.model_validate_json(process.stdout)
            async with Client(
                create_server(self.mcp_root, allow_checks=True), mode="legacy"
            ) as client:
                result = await client.call_tool(
                    "doctor", {"project_id": PROJECT, "electrical": True, "runner": "local"}
                )
                self.assertFalse(result.is_error, result.content)
                mcp_doctor = TemplateDoctorReport.model_validate_json(
                    json.dumps(result.structured_content)
                )
                result = await client.call_tool(
                    "check_project",
                    {"project_id": PROJECT, "depth": "electrical", "runner": "local"},
                )
                self.assertFalse(result.is_error, result.content)
                mcp_check = ProjectVerificationReport.model_validate_json(
                    json.dumps(result.structured_content)
                )
        self.assertEqual(
            [(row.id, row.status, row.observed) for row in cli_doctor.checks],
            [(row.id, row.status, row.observed) for row in mcp_doctor.checks],
        )
        for report in (cli_doctor, mcp_doctor):
            self.assertEqual(report.status, "FAIL")
            self.assertTrue(report.electrical_requested)
            self.assertTrue(report.native_requested)
            self.assertTrue(
                any(row.status == "FAIL" and "ngspice" in row.id for row in report.checks)
            )
        for report in (cli_check, mcp_check):
            self.assertEqual(report.status, "FAIL")
            self.assertEqual(report.depth, "electrical")
            self.assertFalse(report.build_authorized)
            self.assertIsNone(report.native)
            self.assertIsNone(report.electrical)
            self.assertIsNotNone(report.doctor)
            self.assertTrue(report.doctor.electrical_requested)

    async def test_capability_gates_and_file_only_nested_contract_schema(self) -> None:
        gates = {
            "init_electrical": "allow_edits",
            "capture_electrical_inputs": "allow_exports",
            "analyze_electrical": "allow_checks",
            "check_electrical_scope": "allow_checks",
        }
        for flag in (None, "allow_edits", "allow_exports", "allow_checks"):
            async with Client(
                create_server(self.mcp_root, **({flag: True} if flag else {})), mode="legacy"
            ) as client:
                tools = {tool.name: tool for tool in (await client.list_tools()).tools}
                for name, required in gates.items():
                    self.assertEqual(name in tools, flag == required, (name, flag))
                    if name in tools:
                        properties = tools[name].input_schema["properties"]
                        self.assertFalse(
                            {"root", "output", "cli", "ngspice", "contract"} & set(properties)
                        )
                if flag == "allow_exports":
                    bad = await client.call_tool(
                        "capture_electrical_inputs",
                        {
                            "project_id": PROJECT,
                            "view_id": "wrong-model-type",
                            "models": [1],
                        },
                    )
                    self.assertTrue(bad.is_error)
                    self.assertFalse((self.mcp_root / "build/electrical-inputs").exists())

    async def test_typed_sidecar_and_local_models_allow_reviewed_edits_only(self) -> None:
        self.configured(simulation=True)
        sidecar = self.mcp_root / ISLAND / "tests/electrical.json"
        before = sidecar.read_bytes()
        async with Client(create_server(self.mcp_root, allow_edits=True), mode="legacy") as client:
            result = await client.call_tool(
                "read_project_file", {"project_id": PROJECT, "path": "tests/electrical.json"}
            )
            self.assertFalse(result.is_error, result.content)
            for old, new in (
                (f'"project_id": "{PROJECT}"', '"project_id": "another-project"'),
                ('"schema_version": "1"', '"schema_version": "1", "unknown": true'),
            ):
                result = await client.call_tool(
                    "apply_project_edit",
                    {
                        "project_id": PROJECT,
                        "path": "tests/electrical.json",
                        "expected_sha256": digest(sidecar),
                        "old_text": old,
                        "new_text": new,
                    },
                )
                self.assertTrue(result.is_error, result.content)
                self.assertEqual(sidecar.read_bytes(), before)
            old = '"ngspice_version": "47"'
            result = await client.call_tool(
                "apply_project_edit",
                {
                    "project_id": PROJECT,
                    "path": "tests/electrical.json",
                    "expected_sha256": digest(sidecar),
                    "old_text": old,
                    "new_text": '"ngspice_version": "48"',
                },
            )
            self.assertFalse(result.is_error, result.content)
            self.assertIn("--depth electrical", result.structured_content["next_command"])
            changed = read_model(sidecar, ElectricalAnalysisContract)
            self.assertEqual(changed.ngspice_version, "48")
            self.assertEqual(
                changed.power,
                read_model(
                    self.root / ISLAND / "tests/electrical.json", ElectricalAnalysisContract
                ).power,
            )
            approved_sidecar = sidecar.read_bytes()
            model = "tests/electrical/startup.cir"
            read = mcp_files.read_project_file(self.mcp_root, PROJECT, model)
            result = await client.call_tool(
                "apply_project_edit",
                {
                    "project_id": PROJECT,
                    "path": model,
                    "expected_sha256": read.sha256,
                    "old_text": read.text.splitlines()[0],
                    "new_text": "* Explicit reviewed model note",
                },
            )
            self.assertFalse(result.is_error, result.content)
            self.assertEqual(sidecar.read_bytes(), approved_sidecar)
            stale = await client.call_tool(
                "apply_project_edit",
                {
                    "project_id": PROJECT,
                    "path": model,
                    "expected_sha256": read.sha256,
                    "old_text": "* Explicit reviewed model note",
                    "new_text": "* Stale replacement",
                },
            )
            self.assertTrue(stale.is_error)
        report = analyze(self.mcp_root, PROJECT)
        self.assertEqual(report.status, "FAIL")
        self.assertIn("stale reviewed model hash", report.checks[-1].detail)

    async def test_model_and_artifact_boundaries_reject_paths_without_writes(self) -> None:
        for value in (
            "../outside.cir",
            "/tmp/outside.cir",
            "README.md",
            "build/model.cir",
            "examples/projects/another-project/model.cir",
        ):
            with self.subTest(value=value), self.assertRaises((OSError, ValueError)):
                mcp_electrical.capture_electrical_inputs(
                    self.mcp_root, PROJECT, "invalid-model", (value,)
                )
        self.assertFalse((self.mcp_root / "build/electrical-inputs").exists())
        linked = self.mcp_root / ISLAND / "tests/linked.cir"
        linked.symlink_to(self.root / "README.md")
        with self.assertRaises(ValueError):
            mcp_electrical.capture_electrical_inputs(
                self.mcp_root,
                PROJECT,
                "linked-model",
                (linked.relative_to(self.mcp_root).as_posix(),),
            )
        with self.assertRaises(ValueError):
            mcp_files.read_project_file(self.mcp_root, PROJECT, "tests/linked.cir")
        for value in ("README.md", "../outside.json", "/tmp/summary.json"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                mcp_electrical.analyze_electrical(self.mcp_root, PROJECT, "bad-evidence", value)
        self.assertFalse((self.mcp_root / "build/electrical").exists())

    @unittest.skipIf(os.name == "nt", "POSIX FIFO")
    def test_nonregular_model_rejected_before_open_and_stale_deck_rejected(self) -> None:
        contract = install_fixture(self.root)
        case = simulation_cases(contract)[0]
        path = self.root / case.deck
        original = path.read_bytes()
        path.write_bytes(original + b"\n* source changed after review\n")
        with self.assertRaisesRegex(ValueError, "Stale reviewed model hash"):
            expanded_deck(self.root, case)
        path.unlink()
        os.mkfifo(path)
        with patch("kicad_tooling.hwrepo.electrical.os.open") as opened:
            with self.assertRaisesRegex(ValueError, "regular"):
                regular_input_bytes(path)
            with self.assertRaisesRegex(ValueError, "regular"):
                electrical_setup.capture_inputs(self.root, PROJECT, (case.deck,))
            opened.assert_not_called()
        report = analyze(self.root, PROJECT)
        self.assertEqual(report.status, "FAIL")
        self.assertIn("regular", report.checks[-1].detail)


if __name__ == "__main__":
    unittest.main()
