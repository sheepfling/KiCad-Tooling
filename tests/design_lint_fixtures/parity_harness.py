"""Shared temporary project harness for synthetic CLI/MCP parity tests."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import Client

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    CatalogPaths,
    CheckEvidence,
    CommandEvidence,
    ComponentContract,
    ComponentIdentity,
    DesignLintReport,
    IgnoredChecks,
    PcbValidationContract,
    ProjectDiscovery,
    ProjectKind,
    ProjectManifest,
    ProjectTestContract,
    ToolchainRecord,
    ToolchainsCatalog,
    ToolSurfaceReport,
    ValidationSummary,
)
from kicad_tooling.validate import hashes
from tests.design_lint_fixtures.i2c_serial_parity import (
    KICAD_VERSION,
    NETLIST_CONTROL,
    NETLIST_MISSING_ARRAY,
    PROJECT_ID,
    TOOLCHAIN_IMAGE,
    electrical_contract,
)


class I2cSerialParityHarness(unittest.IsolatedAsyncioTestCase):
    """Common source-bound project and adapter setup."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="design-lint-i2c-parity-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repository"
        self.island = self.root / "projects" / PROJECT_ID
        self.source = self.island / "source" / "fixture.json"
        self.native = self.root / "build" / "native" / PROJECT_ID
        self.summary_path = self.native / "summary.json"
        self.netlist_path = self.native / "netlist.xml"
        self.root.mkdir(parents=True)
        self.source.parent.mkdir(parents=True)
        self.native.mkdir(parents=True)
        self._write_repository_configuration()
        self.source.write_text(
            json.dumps({"fixture": "synthetic", "scenario": "control"}) + "\n",
            encoding="utf-8",
        )
        write_model(self.island / "tests" / "contract.json", self._project_contract())
        write_model(self.island / "tests" / "electrical.json", electrical_contract())

    def _project_contract(self) -> ProjectTestContract:
        return ProjectTestContract(
            validation=PcbValidationContract(
                kind=ProjectKind.PCB,
                components={
                    "U1": ComponentContract(value="Synthetic two-wire target", footprint=""),
                    "J1": ComponentContract(
                        value="Synthetic mapped endpoint A", footprint="Synthetic:Header"
                    ),
                    "J2": ComponentContract(
                        value="Synthetic mapped endpoint B", footprint="Synthetic:Header"
                    ),
                    "J3": ComponentContract(
                        value="Synthetic unmapped endpoint", footprint="Synthetic:Header"
                    ),
                    "RN1": ComponentContract(value="4x4.7k", footprint="Synthetic:RA4"),
                },
                nets={
                    "I2C_SDA": ("U1.1", "RN1.1"),
                    "I2C_SCL": ("U1.2", "RN1.3"),
                    "+3V3": ("RN1.2", "RN1.4"),
                    "SERIAL_A_TX": ("J1.1", "J2.2"),
                    "SERIAL_A_RX": ("J1.2", "J2.1"),
                    "SERIAL_B_TX": ("J3.1",),
                    "SERIAL_B_RX": ("J3.2",),
                },
                expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
            ),
            electrical="tests/electrical.json",
        )

    def _write_repository_configuration(self) -> None:
        (self.root / "catalog").mkdir(parents=True, exist_ok=True)
        (self.island / "tests").mkdir(parents=True, exist_ok=True)
        catalogs = CatalogPaths(
            parts="catalog/parts.json",
            interfaces="catalog/interfaces.json",
            libraries="catalog/libraries.json",
            toolchains="catalog/toolchains.json",
            release_policies="catalog/release-policies.json",
        )
        write_model(
            self.root / "catalog" / "projects.json",
            ProjectDiscovery(catalogs=catalogs, project_roots=("projects",), project_depth=1),
        )
        write_model(
            self.root / "catalog" / "toolchains.json",
            ToolchainsCatalog(
                schema_version="1",
                toolchains=(
                    ToolchainRecord(
                        id="synthetic-kicad-10-0-5",
                        kicad_version=KICAD_VERSION,
                        image=TOOLCHAIN_IMAGE,
                        desktop_edit_policy="Synthetic fixture only",
                        installer_source="Synthetic fixture only",
                        migration_policy="Synthetic fixture only",
                    ),
                ),
            ),
        )
        write_model(
            self.island / "project.json",
            ProjectManifest(
                id=PROJECT_ID,
                kind=ProjectKind.PCB,
                status="training_fixture",
                assurance_profile="training",
                toolchain_id="synthetic-kicad-10-0-5",
                project="design.kicad_pro",
                source_roots=("source",),
                required_inputs=("source/fixture.json",),
                component_identity=ComponentIdentity(required=False, part_ids=()),
            ),
        )

    def _write_native_evidence(
        self, *, missing_array: bool, netlist_xml: str | None = None
    ) -> None:
        scenario = "missing-pull-up-array" if missing_array else "mapped-array-control"
        if netlist_xml is not None:
            scenario = "alternate-function-uart-labels"
        self.source.write_text(
            json.dumps({"fixture": "synthetic", "scenario": scenario}) + "\n",
            encoding="utf-8",
        )
        self.netlist_path.write_text(
            netlist_xml
            if netlist_xml is not None
            else NETLIST_MISSING_ARRAY
            if missing_array
            else NETLIST_CONTROL,
            encoding="utf-8",
        )
        command = CommandEvidence(
            argv=("synthetic-netlist-fixture", scenario),
            started_utc="2026-09-30T00:00:00+00:00",
            returncode=0,
        )
        write_model(self.native / "netlist.command.json", command)
        source_hashes = hashes(self.root, (f"projects/{PROJECT_ID}/source",))
        write_model(
            self.summary_path,
            ValidationSummary(
                timestamp_utc="2026-09-30T00:00:00+00:00",
                checked_commit="SYNTHETIC_FIXTURE_NOT_A_RELEASE_COMMIT",
                project_id=PROJECT_ID,
                project_kind=ProjectKind.PCB,
                checks={
                    "source_scope": CheckEvidence(status="PASS", source_hashes=source_hashes),
                    "source_unchanged": CheckEvidence(status="PASS", source_hashes=source_hashes),
                    "toolchain": CheckEvidence(
                        status="PASS",
                        observed_version=KICAD_VERSION,
                        image=TOOLCHAIN_IMAGE,
                    ),
                    "netlist": CheckEvidence(
                        status="FAIL" if missing_array else "PASS",
                        returncode=0,
                        error=("Synthetic missing-array fault" if missing_array else None),
                    ),
                },
                status="FAIL" if missing_array else "PASS",
                artifacts_sha256={
                    "netlist.xml": digest(self.netlist_path),
                    "netlist.command.json": digest(self.native / "netlist.command.json"),
                },
            ),
        )

    async def _inspect_both_surfaces(self, client: Client) -> DesignLintReport:
        native_relative = self.summary_path.relative_to(self.root).as_posix()
        mcp_result = await client.call_tool(
            "inspect_design_lint",
            {"project_id": PROJECT_ID, "native_summary": native_relative},
        )
        self.assertFalse(mcp_result.is_error, mcp_result.content)
        self.assertIsNotNone(mcp_result.structured_content)
        mcp_report = DesignLintReport.model_validate_json(json.dumps(mcp_result.structured_content))

        process = await asyncio.to_thread(
            subprocess.run,
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.design_lint",
                "--root",
                str(self.root),
                "--project",
                PROJECT_ID,
                "--native-summary",
                str(self.summary_path),
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
        self.assertIn(process.returncode, (0, 1), process.stderr + process.stdout)
        cli_report = DesignLintReport.model_validate_json(process.stdout)
        self.assertEqual(process.returncode, int(cli_report.status != "PASS"), process.stderr)
        self.assertEqual(cli_report, mcp_report)
        return mcp_report

    async def _check_surface_registration(self) -> None:
        process = await asyncio.to_thread(
            subprocess.run,
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.surface",
                "--root",
                str(self.root),
                "--require-live-mcp",
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
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        surface = ToolSurfaceReport.model_validate_json(process.stdout)
        self.assertEqual(surface.parity_status, "PASS", surface.issues)
        self.assertEqual(surface.mcp_verification, "LIVE")
