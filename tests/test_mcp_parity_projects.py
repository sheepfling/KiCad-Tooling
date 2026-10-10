"""Project workflow CLI/MCP parity cases: mcp parity projects."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.parity_lint, pytest.mark.slow, pytest.mark.template_checkout]

import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from kicad_tooling.hwrepo.contracts import (
    read_model,
    write_model,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    CheckAllSummary,
    ContractCoachReport,
    DiagnosticReport,
    LocalRescueReport,
    ProjectScaffoldReport,
    ProjectStaticPipelineReport,
    ProjectVerificationReport,
    ValidationSummary,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)


class _McpParityProjectsCases(McpParityHarness):
    async def _case_test_missing_electrical_requirements_are_visible_without_claiming_failure(
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

    async def _case_test_project_diagnosis_parity(self) -> None:
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

    async def _case_test_rescue_parity(self) -> None:
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

    async def _case_test_selected_verification_parity(self) -> None:
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

    async def _case_test_scope_check_parity(self) -> None:
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

    async def _case_test_tag_shard_scope_check_parity(self) -> None:
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

    async def _case_test_native_scope_failure_parity(self) -> None:
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

    async def _case_test_new_project_parity(self) -> None:
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

    async def _case_test_contract_inspection_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            '<export><components><comp ref="J1"><value>Synthetic port</value>'
            '<libsource lib="Synthetic" part="Port"/><units><unit name="A"><pins>'
            '<pin num="1"/><pin num="7"/></pins></unit></units></comp>'
            '<comp ref="J2"><value>Synthetic port</value>'
            '<libsource lib="Synthetic" part="Port"/><units><unit name="A"><pins>'
            '<pin num="1"/><pin num="7"/></pins></unit></units></comp></components>'
            '<libparts><libpart lib="Synthetic" part="Port"><pins>'
            '<pin num="1" name="PWR" type="passive"/>'
            '<pin num="7" name="GND" type="passive"/></pins></libpart></libparts><nets>'
            '<net name="0V CTRL 1"><node ref="J1" pin="7"/></net>'
            '<net name="0V CTRL 2"><node ref="J2" pin="7"/></net>'
            '<net name="+5V"><node ref="J1" pin="1"/></net>'
            "</nets></export>",
            encoding="utf-8",
        )
        summary = read_model(native, ValidationSummary)
        write_model(
            native,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(netlist),
                    }
                }
            ),
        )
        async with Client(create_server(self.root), mode="legacy") as client:
            for case in ("valid", "empty", "tampered"):
                with self.subTest(case=case):
                    if case == "empty":
                        netlist.write_text(
                            "<export><components/><nets/></export>", encoding="utf-8"
                        )
                        summary = read_model(native, ValidationSummary)
                        write_model(
                            native,
                            summary.model_copy(
                                update={
                                    "artifacts_sha256": {
                                        **summary.artifacts_sha256,
                                        "netlist.xml": digest(netlist),
                                    }
                                }
                            ),
                        )
                    elif case == "tampered":
                        (native.parent / "netlist.xml").write_text("<export/>", encoding="utf-8")
                    cli = await self.cli(
                        "kicad_tooling.contract_coach",
                        ContractCoachReport,
                        "--project-id",
                        "controller",
                        "--native-summary",
                        str(native),
                        expected_exit=int(case != "valid"),
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
                    self.assertEqual(
                        mcp.status, "READY_FOR_REVIEW" if case == "valid" else "BLOCKED"
                    )
                    if case == "valid":
                        self.assertEqual(mcp.native_status, "FAIL")
                        self.assertEqual(mcp.review_state, "UNREVIEWED")
                        self.assertEqual(
                            set(mcp.return_net_groups[0].nets), {"0V CTRL 1", "0V CTRL 2"}
                        )
                        power = next(
                            group
                            for group in mcp.similar_connector_pin_groups
                            if group.function == "PWR"
                        )
                        self.assertEqual(power.pins["J2.1"], ())
                        self.assertIn("approved connector pinout", " ".join(mcp.next_actions))
                    elif case == "empty":
                        self.assertIn("contains no component records", mcp.issues[0])
                        self.assertIsNone(mcp.observed)
                    self.assertFalse(mcp.electrical_coverage)


def test_missing_electrical_requirements_are_visible_without_claiming_failure() -> None:
    run_mcp_parity(
        _McpParityProjectsCases,
        "_case_test_missing_electrical_requirements_are_visible_without_claiming_failure",
    )


def test_project_diagnosis_parity() -> None:
    run_mcp_parity(_McpParityProjectsCases, "_case_test_project_diagnosis_parity")


def test_rescue_parity() -> None:
    run_mcp_parity(_McpParityProjectsCases, "_case_test_rescue_parity")


def test_selected_verification_parity() -> None:
    run_mcp_parity(_McpParityProjectsCases, "_case_test_selected_verification_parity")


def test_scope_check_parity() -> None:
    run_mcp_parity(_McpParityProjectsCases, "_case_test_scope_check_parity")


def test_tag_shard_scope_check_parity() -> None:
    run_mcp_parity(_McpParityProjectsCases, "_case_test_tag_shard_scope_check_parity")


def test_native_scope_failure_parity() -> None:
    run_mcp_parity(_McpParityProjectsCases, "_case_test_native_scope_failure_parity")


def test_new_project_parity() -> None:
    run_mcp_parity(_McpParityProjectsCases, "_case_test_new_project_parity")


def test_contract_inspection_parity() -> None:
    run_mcp_parity(_McpParityProjectsCases, "_case_test_contract_inspection_parity")
