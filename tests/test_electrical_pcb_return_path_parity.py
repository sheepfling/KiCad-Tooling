"""CLI/MCP parity for reviewed PCB return-path requirements."""

from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import patch

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, repo_path, write_model
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    PcbReturnDomainRequirement,
    PcbReturnEndpointRequirement,
    PcbReturnPathsAnalysis,
)
from tests.contract_coach_support import fake_executable
from tests.electrical_parity_support import parity_harness  # noqa: F401
from tests.electrical_simulation_support import ISLAND, PROJECT
from tests.test_source_parity import source_bytes

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.return_path_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


async def _run_pcb_return_path_contract_matches_cli_and_mcp(parity) -> None:
    parity.configured()
    requirement = PcbReturnPathsAnalysis(
        basis="Synthetic independently reviewed connector return pinout",
        domains=(
            PcbReturnDomainRequirement(
                id="serial-returns",
                basis="Synthetic DB9 common-return requirement",
                topology="direct",
                endpoints=(
                    PcbReturnEndpointRequirement(
                        pad="J1.7", net="0V_PWM", footprint="Synthetic:DB9"
                    ),
                    PcbReturnEndpointRequirement(
                        pad="J2.7", net="0V_PWM", footprint="Synthetic:DB9"
                    ),
                ),
            ),
        ),
    )
    board_source = (
        '(kicad_pcb (version 20250114) (net 0 "") (net 1 "0V_PWM") '
        '(footprint "Synthetic:DB9" (layer "F.Cu") (property "Reference" "J1") '
        '(pad "7" thru_hole circle (at 0 0) (size 1 1) '
        '(layers "*.Cu" "*.Mask") (net 1 "0V_PWM"))) '
        '(footprint "Synthetic:DB9" (layer "F.Cu") (property "Reference" "J2") '
        '(pad "7" thru_hole circle (at 2 0) (size 1 1) '
        '(layers "*.Cu" "*.Mask") (net 1 "0V_PWM"))))'
    )
    config = selected_config(parity.root, PROJECT)
    for root in (parity.root, parity.mcp_root):
        contract_path = root / ISLAND / "tests/electrical.json"
        contract = read_model(contract_path, ElectricalAnalysisContract).model_copy(
            update={"pcb_return_paths": requirement}
        )
        write_model(contract_path, contract)
        board_path = repo_path(root, config.project).with_suffix(".kicad_pcb")
        board_path.write_text(board_source, encoding="utf-8")

    fake_bin = parity.root.parent / "fake-pcb-docker"
    fake_bin.mkdir()
    fake_docker = fake_executable(
        fake_bin / "docker",
        "from __future__ import annotations\n"
        "import hashlib, json, os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "work = Path(next(arg[:-len(':/work:ro')] for arg in args if arg.endswith(':/work:ro')))\n"
        "output = Path(next(arg[:-len(':/output:rw')] for arg in args if arg.endswith(':/output:rw')))\n"
        "board = work / args[-2].removeprefix('/work/')\n"
        "snapshot = output / args[-1].removeprefix('/output/')\n"
        "connected = os.environ.get('FAKE_PCB_CONNECTIVITY') == 'connected'\n"
        "group = ['J1.7', 'J2.7'] if connected else None\n"
        "rows = []\n"
        "for name in ('J1.7', 'J2.7'):\n"
        "    rows.append({'pad': name, 'net': '0V_PWM', 'footprint': 'Synthetic:DB9', "
        "'dnp': False, 'connected_pads': group or [name], 'connected_zones': [], "
        "'connected_islands': []})\n"
        "data = {'schema_version': '2', 'board_sha256': hashlib.sha256(board.read_bytes()).hexdigest(), "
        f"'kicad_version': {config.kicad_version!r}, "
        "'zones_refilled': True, 'pads': rows, 'net_ties': [], 'zones': []}\n"
        "snapshot.write_text(json.dumps(data, sort_keys=True), encoding='utf-8')\n",
    )
    before = source_bytes(parity.root)

    async def analyze_pair(view: str, connected: bool) -> None:
        with patch.dict(
            os.environ,
            {
                "PATH": str(fake_docker.parent) + os.pathsep + os.environ.get("PATH", ""),
                "FAKE_PCB_CONNECTIVITY": "connected" if connected else "disconnected",
            },
        ):
            process = await parity.cli(
                "kicad_tooling.electrical",
                "--project",
                PROJECT,
                "--output",
                f"build/electrical/{view}",
            )
            expected_exit = 0 if connected else 1
            assert process.returncode == expected_exit, process.stderr + process.stdout
            cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
            async with Client(
                create_server(parity.mcp_root, allow_checks=True), mode="legacy"
            ) as client:
                result = await client.call_tool(
                    "analyze_electrical",
                    {"project_id": PROJECT, "view_id": view},
                )
            assert not result.is_error, result.content
            mcp_report = ElectricalAnalysisReport.model_validate_json(
                json.dumps(result.structured_content)
            )
        assert cli_report.checks == mcp_report.checks
        assert cli_report.input_sha256 == mcp_report.input_sha256
        wanted = "PASS" if connected else "FAIL"
        for report in (cli_report, mcp_report):
            assert report.status == wanted
            check = next(
                row
                for row in report.checks
                if row.id == "pcb-return-paths/serial-returns/connectivity"
            )
            assert check.status == wanted
            assert "pcb-connectivity" in report.commands

    await analyze_pair("pcb-return-pass", True)
    await analyze_pair("pcb-return-fault", False)
    assert source_bytes(parity.root) == before
    assert source_bytes(parity.mcp_root) == before


def test_pcb_return_path_contract_matches_cli_and_mcp_for_pass_and_fault(parity) -> None:
    asyncio.run(_run_pcb_return_path_contract_matches_cli_and_mcp(parity))
