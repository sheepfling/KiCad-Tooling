"""CLI/MCP parity for schematic and PCB test-access requirements."""

from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import patch

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, repo_path, write_model
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    PcbAccessAnalysis,
    RequiredTestAccess,
    ValidationSummary,
)
from kicad_tooling.hwrepo.models import (
    TestAccessAnalysis as AccessAnalysis,
)
from kicad_tooling.hwrepo.models import (
    TestAccessEndpointRequirement as AccessEndpointRequirement,
)
from kicad_tooling.hwrepo.models import (
    TestAccessProbeEnvelope as AccessProbeEnvelope,
)
from kicad_tooling.validate import hashes
from tests.contract_coach_support import fake_executable
from tests.electrical_parity_support import (
    ElectricalParityHarness,
    contract_netlist_xml,
    parity_harness,  # noqa: F401
)
from tests.electrical_simulation_support import ISLAND, PROJECT
from tests.test_control_inputs import control_netlist

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.evidence_lint,
    pytest.mark.pcb_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


def _testpoint_board_source() -> str:
    return (
        '(kicad_pcb (version 20250114) (net 0 "") (net 1 "+3V3") (net 2 "OTHER") '
        '(footprint "TestPoint:TestPoint_Pad_D1.0mm" (layer "F.Cu") '
        '(property "Reference" "TP1") '
        '(pad "1" smd circle (at 0 0) (size 1 1) '
        '(layers "F.Cu" "F.Mask") (net 1 "+3V3"))) '
        '(footprint "Synthetic:Obstacle" (layer "F.Cu") (at 1 0) '
        '(property "Reference" "TP2") '
        '(pad "1" smd circle (at 0 0) (size 1 1) '
        '(layers "F.Cu" "F.Mask") (net 2 "OTHER"))))'
    )


async def _run_test_access_schematic_and_board_stages_match_cli_and_mcp(
    parity: ElectricalParityHarness,
) -> None:
    parity.configured()
    access = AccessAnalysis(
        basis="Synthetic manufacturing access requirements",
        pcb_accessibility=PcbAccessAnalysis(
            basis="Synthetic probe pad must be placed and mask-open"
        ),
        decisions=(
            RequiredTestAccess(
                mode="required",
                id="logic-rail",
                basis="Synthetic fixture measures the logic rail",
                net="+3V3",
                endpoints=(
                    AccessEndpointRequirement(
                        kind="test_point",
                        reference="TP1",
                        symbol="TestPoint:TestPoint",
                        footprint="TestPoint:TestPoint_Pad_D1.0mm",
                        pin="TP1.1",
                        electrical_type="passive",
                        approach_side="front",
                        probe_envelope=AccessProbeEnvelope(
                            tip_diameter_mm=0.8,
                            clearance_mm=0.1,
                        ),
                    ),
                ),
            ),
        ),
    )
    for root in (parity.root, parity.mcp_root):
        contract_path = root / ISLAND / "tests/electrical.json"
        contract = read_model(contract_path, ElectricalAnalysisContract)
        write_model(contract_path, contract.model_copy(update={"test_access": access}))
        config = selected_config(root, PROJECT)
        board_path = repo_path(root, config.project).with_suffix(".kicad_pcb")
        board_path.write_text(_testpoint_board_source(), encoding="utf-8")
        native = root / "build/native/controller"
        netlist = native / "netlist.xml"
        netlist.write_text(contract_netlist_xml(control_netlist()), encoding="utf-8")
        summary_path = native / "summary.json"
        summary = read_model(summary_path, ValidationSummary)
        current_hashes = hashes(root, config.source_roots)
        summary_checks = dict(summary.checks)
        for check_id in ("source_scope", "source_unchanged"):
            summary_checks[check_id] = summary_checks[check_id].model_copy(
                update={"source_hashes": current_hashes}
            )
        write_model(
            summary_path,
            summary.model_copy(
                update={
                    "checks": summary_checks,
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(netlist),
                    },
                }
            ),
        )

    fake_bin = parity.root.parent / "fake-access-probe"
    fake_bin.mkdir()
    fake_docker = fake_executable(
        fake_bin / "docker",
        "from __future__ import annotations\n"
        "import hashlib, json, os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "work = Path(next(arg[:-len(':/work:ro')] for arg in args if arg.endswith(':/work:ro')))\n"
        "output = Path(next(arg[:-len(':/output:rw')] for arg in args if arg.endswith(':/output:rw')))\n"
        "board = work / args[-3].removeprefix('/work/')\n"
        "snapshot = output / args[-2].removeprefix('/output/')\n"
        "request = output / args[-1].removeprefix('/output/')\n"
        "rows = json.loads(request.read_text(encoding='utf-8'))['requests']\n"
        "distance = int(os.environ['FAKE_ACCESS_DISTANCE_NM'])\n"
        "data = {'schema_version': '10', 'board_sha256': hashlib.sha256(board.read_bytes()).hexdigest(), "
        f"'kicad_version': {config.kicad_version!r}, "
        "'zones_refilled': True, 'pads': ["
        "{'pad': 'TP1.1', 'net': '+3V3', 'footprint': 'TestPoint:TestPoint_Pad_D1.0mm', 'dnp': False, 'connected_pads': ['TP1.1'], 'connected_vias': [], 'connected_zones': [], 'connected_islands': [], 'positions_nm': [[0, 0]]}, "
        "{'pad': 'TP2.1', 'net': 'OTHER', 'footprint': 'Synthetic:Obstacle', 'dnp': False, 'connected_pads': ['TP2.1'], 'connected_vias': [], 'connected_zones': [], 'connected_islands': [], 'positions_nm': [[500000, 0]]}], "
        "'vias': [], 'net_ties': [], 'zones': [], 'tracks': [], 'copper_layers': ['F.Cu', 'B.Cu'], 'access_probe_observations': ["
        "{'endpoint': item['endpoint'], 'side': item['side'], 'target_net': item['net'], 'target_exposed': True, 'obstacle': 'TP2.1', 'obstacle_net': 'OTHER', 'distance_nm': distance, 'target_aperture_shape': 'circle', 'target_aperture_diameter_nm': 1000000} for item in rows], "
        "'access_probe_requests_sha256': hashlib.sha256(request.read_bytes()).hexdigest()}\n"
        "snapshot.write_text(json.dumps(data, sort_keys=True), encoding='utf-8')\n",
    )
    assert fake_docker.exists()
    summary_arg = "build/native/controller/summary.json"

    async def analyze_pair(view: str, distance_nm: int, expected: str) -> None:
        with patch.dict(
            os.environ,
            {
                "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", ""),
                "FAKE_ACCESS_DISTANCE_NM": str(distance_nm),
            },
        ):
            process = await parity.cli(
                "kicad_tooling.electrical",
                "--project",
                PROJECT,
                "--native-summary",
                summary_arg,
                "--output",
                f"build/electrical/{view}",
            )
            assert process.returncode == (0 if expected == "PASS" else 1), (
                process.stderr + process.stdout
            )
            cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
            async with Client(
                create_server(parity.mcp_root, allow_checks=True), mode="legacy"
            ) as client:
                result = await client.call_tool(
                    "analyze_electrical",
                    {
                        "project_id": PROJECT,
                        "view_id": view,
                        "native_summary": summary_arg,
                    },
                )
        assert not result.is_error, result.content
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        assert cli_report.checks == mcp_report.checks
        assert set(cli_report.commands) == set(mcp_report.commands)
        for report in (cli_report, mcp_report):
            check = next(
                row
                for row in report.checks
                if row.id == "test-access/pcb-probe-envelope/logic-rail"
            )
            assert check.status == expected
            assert "target mask aperture is 1 mm" in check.detail
            assert "required tip-plus-clearance diameter is 1 mm" in check.detail
            assert "pcb-connectivity" in report.commands

    await analyze_pair("pcb-test-access-pass", 500_000, "PASS")
    await analyze_pair("pcb-test-access-fault", 499_999, "FAIL")


def test_test_access_schematic_and_board_stages_match_cli_and_mcp(
    parity: ElectricalParityHarness,
) -> None:
    asyncio.run(_run_test_access_schematic_and_board_stages_match_cli_and_mcp(parity))
