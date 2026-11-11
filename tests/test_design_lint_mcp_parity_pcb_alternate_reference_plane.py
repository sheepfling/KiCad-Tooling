"""CLI/MCP parity for the opt-in alternate reference-plane review."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    PcbReferencePlaneMap,
    PcbReferencePlaneRequirement,
    ProjectTestContract,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    pcb_native_snapshot_shim,
    run_mcp_parity,
)

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.return_path_lint,
]


class _AlternateReferencePlaneParityCases(McpParityHarness):
    async def _case_test_alternate_reference_plane_rule_matches_cli_and_mcp(self) -> None:
        """Exercise the opt-in alternate-net finding through both public adapters."""
        fixture = (
            Path(__file__).parents[1]
            / "kicad_tooling/hwrepo/fixtures/pcb-reference-alternate-net.kicad_pcb"
        )
        shutil.copyfile(fixture, self.island / "kicad/controller.kicad_pcb")
        native = self.native_evidence()
        policy = DesignLintPolicy(
            pcb_reference_plane_map=PcbReferencePlaneMap(
                basis="Synthetic alternate-net CLI/MCP parity map",
                requirements=(
                    PcbReferencePlaneRequirement(
                        id="synthetic-data-alternate-net",
                        basis="Synthetic adjacent VCC coverage review",
                        signal_net="DATA",
                        signal_layers=("F.Cu",),
                        reference_net="GND",
                        minimum_track_length_um=1,
                        minimum_referenced_fraction=0,
                        minimum_alternate_reference_length_um=400,
                    ),
                ),
            )
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(contract_path, contract.model_copy(update={"design_lint": policy}))

        shim = self.base / "alternate-plane-docker-shim"
        shim.mkdir()
        docker = shim / "docker"
        docker.write_text(pcb_native_snapshot_shim(), encoding="utf-8")
        docker.chmod(0o755)
        environment = {
            "PATH": os.pathsep.join((str(shim), os.environ["PATH"])),
            "KICAD_TEST_ALTERNATE_REFERENCE_PLANE": "1",
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            with patch.dict(os.environ, environment):
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=1,
                )
                mcp = await self.call(
                    client,
                    "inspect_design_lint",
                    DesignLintReport,
                    {
                        "project_id": "controller",
                        "native_summary": native.relative_to(self.root).as_posix(),
                    },
                )
        self.assertEqual(self.semantic(cli), self.semantic(mcp))
        finding = next(
            item for item in mcp.findings if item.rule_id == "pcb.alternate_reference_plane_run"
        )
        self.assertEqual(finding.mode, "review")
        self.assertEqual(finding.evidence["alternate_net"], ("VCC",))
        self.assertEqual(finding.evidence["minimum_alternate_reference_length_um"], ("400",))
        self.assertEqual(
            finding.evidence["alternate_reference_intervals"],
            ("00000000-0000-0000-0000-000000000103:2500000,2000000nm->3000000,2000000nm",),
        )


def test_alternate_reference_plane_rule_matches_cli_and_mcp() -> None:
    run_mcp_parity(
        _AlternateReferencePlaneParityCases,
        "_case_test_alternate_reference_plane_rule_matches_cli_and_mcp",
    )
