"""CLI/MCP parity for reviewed serial-peer contracts."""

from __future__ import annotations

import asyncio
import json

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    ValidationSummary,
)
from kicad_tooling.hwrepo.serial_peer_models import SerialPeerAnalysis
from tests.electrical_parity_support import contract_netlist_xml, parity_harness  # noqa: F401
from tests.electrical_serial_support import serial_peer_netlist, serial_peer_requirement
from tests.test_electrical import ISLAND, PROJECT

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


def _install_serial_evidence(parity, requirement: SerialPeerAnalysis, observed) -> None:
    """Bind one synthetic serial contract and netlist to both test repositories."""
    serialized = contract_netlist_xml(observed)
    for root in (parity.root, parity.mcp_root):
        contract_path = root / ISLAND / "tests/electrical.json"
        contract = read_model(contract_path, ElectricalAnalysisContract)
        write_model(
            contract_path,
            contract.model_copy(update={"serial_peers": requirement}),
        )
        netlist = root / "build/native/controller/netlist.xml"
        netlist.write_text(serialized, encoding="utf-8")
        summary_path = root / "build/native/controller/summary.json"
        summary = read_model(summary_path, ValidationSummary)
        write_model(
            summary_path,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(netlist),
                    }
                }
            ),
        )


async def _analyze_both(parity, view_id: str) -> tuple[ElectricalAnalysisReport, int]:
    """Run one source-bound view through CLI and MCP and compare the checks."""
    summary = "build/native/controller/summary.json"
    process = await parity.cli(
        "kicad_tooling.electrical",
        "--project",
        PROJECT,
        "--native-summary",
        summary,
        "--output",
        f"build/electrical/{view_id}",
    )
    cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
    async with Client(create_server(parity.mcp_root, allow_checks=True), mode="legacy") as client:
        result = await client.call_tool(
            "analyze_electrical",
            {"project_id": PROJECT, "view_id": view_id, "native_summary": summary},
        )
    assert not result.is_error, result.content
    mcp_report = ElectricalAnalysisReport.model_validate_json(
        json.dumps(result.structured_content)
    )
    assert cli_report.checks == mcp_report.checks
    return cli_report, process.returncode


async def _run_serial_peer_requirements(parity) -> None:
    parity.configured()
    requirement = serial_peer_requirement(endpoint_reference="U10", peer_reference="U11")
    observed = serial_peer_netlist(requirement)
    _install_serial_evidence(parity, requirement, observed)

    passed, pass_returncode = await _analyze_both(parity, "serial-peer-pass")
    assert pass_returncode == 0
    pass_checks = {row.id: row for row in passed.checks}
    assert pass_checks["serial/console-link/route/a_tx_to_b_rx"].status == "PASS"
    assert pass_checks["serial/console-link/route/b_tx_to_a_rx"].status == "PASS"
    assert pass_checks["serial/console-link/reference"].status == "PASS"

    voltage_requirement = serial_peer_requirement(peer_output_high_maximum_v=5.0)
    _install_serial_evidence(parity, voltage_requirement, observed)
    voltage_fault, voltage_returncode = await _analyze_both(parity, "serial-voltage-fault")
    assert voltage_returncode == 1
    voltage_checks = {row.id: row for row in voltage_fault.checks}
    assert voltage_checks["serial/console-link/logic-voltage/b_tx_to_a_rx"].status == "FAIL"

    wrong_routes = serial_peer_netlist(requirement, fault="tx-to-tx")
    _install_serial_evidence(parity, requirement, wrong_routes)
    route_fault, route_returncode = await _analyze_both(parity, "serial-peer-fault")
    assert route_returncode == 1
    route_checks = {row.id: row for row in route_fault.checks}
    assert route_checks["serial/console-link/route/a_tx_to_b_rx"].status == "FAIL"
    assert route_checks["serial/console-link/route/b_tx_to_a_rx"].status == "FAIL"


def test_serial_peer_requirements_match_cli_and_mcp(parity) -> None:
    asyncio.run(_run_serial_peer_requirements(parity))


async def _run_serial_bonded_reference(parity) -> None:
    parity.configured()
    requirement = serial_peer_requirement(reference_policy="bonded")

    _install_serial_evidence(parity, requirement, serial_peer_netlist(requirement))
    control, control_returncode = await _analyze_both(parity, "serial-bond-control")
    assert control_returncode == 0
    control_checks = {item.id: item for item in control.checks}
    assert control_checks["serial/console-link/reference"].status == "PASS"

    fault_netlist = serial_peer_netlist(requirement, fault="bond-wrong-net")
    _install_serial_evidence(parity, requirement, fault_netlist)
    fault, fault_returncode = await _analyze_both(parity, "serial-bond-fault")
    assert fault_returncode == 1
    reference_check = {item.id: item for item in fault.checks}["serial/console-link/reference"]
    assert reference_check.status == "FAIL"
    assert "R3.2 is on FLOATING_GND; expected GND_B" in reference_check.detail


def test_serial_peer_bonded_reference_matches_cli_and_mcp_for_pass_and_fault(parity) -> None:
    asyncio.run(_run_serial_bonded_reference(parity))
