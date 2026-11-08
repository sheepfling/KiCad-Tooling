"""CLI/MCP parity for project-mapped reference-zone island review."""

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


class _ReferencePlaneIslandParityCases(McpParityHarness):
    async def _case_test_unanchored_reference_island_rule_matches_cli_and_mcp(self) -> None:
        """Exercise the project-mapped finding through both public adapters."""
        fixture = (
            Path(__file__).parents[1]
            / "tests/fixtures/design_lint/pcb-reference-zone-island/fault.kicad_pcb"
        )
        shutil.copyfile(fixture, self.island / "kicad/controller.kicad_pcb")
        native = self.native_evidence()
        policy = DesignLintPolicy(
            pcb_reference_plane_map=PcbReferencePlaneMap(
                basis="Synthetic reference-island CLI/MCP review map",
                requirements=(
                    PcbReferencePlaneRequirement(
                        id="synthetic-data-return",
                        basis="Synthetic B.Cu DATA route against adjacent F.Cu RETURN copper",
                        signal_net="DATA",
                        signal_layers=("B.Cu",),
                        reference_net="RETURN",
                        minimum_track_length_um=1_000,
                        minimum_referenced_fraction=1,
                        review_unanchored_islands=True,
                    ),
                ),
            )
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(contract_path, contract.model_copy(update={"design_lint": policy}))

        shim = self.base / "reference-island-docker-shim"
        shim.mkdir()
        docker = shim / "docker"
        docker.write_text(pcb_native_snapshot_shim(), encoding="utf-8")
        docker.chmod(0o755)
        environment = {
            "PATH": os.pathsep.join((str(shim), os.environ["PATH"])),
            "KICAD_TEST_REFERENCE_PLANE_ISLAND": "1",
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
        cli_semantic = self.semantic(cli)
        mcp_semantic = self.semantic(mcp)
        differences = []

        def compare(left, right, path="$"):
            if left == right or len(differences) >= 12:
                return
            if isinstance(left, dict) and isinstance(right, dict):
                for key in sorted(left.keys() | right.keys()):
                    compare(left.get(key), right.get(key), f"{path}.{key}")
                return
            if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
                for index, (first, second) in enumerate(zip(left, right, strict=True)):
                    compare(first, second, f"{path}[{index}]")
                return
            differences.append((path, repr(left)[:240], repr(right)[:240]))

        compare(cli_semantic, mcp_semantic)
        assert not differences, differences
        matching = tuple(
            item for item in mcp.findings if item.rule_id == "pcb.reference_plane_unanchored_island"
        )
        assert matching, {
            "rule_ids": tuple(item.rule_id for item in mcp.findings),
            "reference_plane": mcp.pcb_reference_plane,
        }
        finding = matching[0]
        self.assertEqual(finding.mode, "review")
        self.assertEqual(finding.evidence["reference_net"], ("RETURN",))
        self.assertEqual(finding.evidence["reference_layer"], ("F.Cu",))
        self.assertEqual(finding.evidence["island_index"], ("0",))


@pytest.mark.design_lint_rule(rule_id="pcb.reference_plane_unanchored_island")
def test_unanchored_reference_island_rule_matches_cli_and_mcp() -> None:
    run_mcp_parity(
        _ReferencePlaneIslandParityCases,
        "_case_test_unanchored_reference_island_rule_matches_cli_and_mcp",
    )
