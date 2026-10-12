"""CLI/MCP parity for authored RS-485 topology requirements."""

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
from tests.electrical_parity_support import (
    ElectricalParityHarness,
    contract_netlist_xml,
    parity_harness,  # noqa: F401
)
from tests.electrical_rs485_support import rs485_netlist, rs485_requirement
from tests.electrical_simulation_support import ISLAND, PROJECT

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


async def _run_rs485_contract_matches_cli_and_mcp_for_pass_and_fault(
    parity: ElectricalParityHarness,
) -> None:
    parity.configured()
    requirement = rs485_requirement()
    observed = rs485_netlist(requirement)
    for root in (parity.root, parity.mcp_root):
        contract_path = root / ISLAND / "tests/electrical.json"
        contract = read_model(contract_path, ElectricalAnalysisContract)
        write_model(contract_path, contract.model_copy(update={"rs485": requirement}))
        native = root / "build/native/controller"
        netlist = native / "netlist.xml"
        netlist.write_text(contract_netlist_xml(observed), encoding="utf-8")
        summary_path = native / "summary.json"
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

    summary_arg = "build/native/controller/summary.json"
    process = await parity.cli(
        "kicad_tooling.electrical",
        "--project",
        PROJECT,
        "--native-summary",
        summary_arg,
        "--output",
        "build/electrical/rs485-pass",
    )
    assert process.returncode == 0, process.stderr + process.stdout
    cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
    async with Client(create_server(parity.mcp_root, allow_checks=True), mode="legacy") as client:
        result = await client.call_tool(
            "analyze_electrical",
            {"project_id": PROJECT, "view_id": "rs485-pass", "native_summary": summary_arg},
        )
    assert not result.is_error, result.content
    mcp_report = ElectricalAnalysisReport.model_validate_json(json.dumps(result.structured_content))
    assert cli_report.checks == mcp_report.checks
    checks = {row.id: row for row in cli_report.checks}
    assert checks["rs485/fieldbus/pair/shared/membership"].status == "PASS"
    assert checks["rs485/fieldbus/pair/shared/termination/local-end"].status == "PASS"
    assert checks["rs485/fieldbus/pair/shared/bias"].status == "PASS"

    faulty = contract_netlist_xml(rs485_netlist(requirement, fault="termination-dnp"))
    for root in (parity.root, parity.mcp_root):
        native = root / "build/native/controller"
        netlist = native / "netlist.xml"
        netlist.write_text(faulty, encoding="utf-8")
        summary_path = native / "summary.json"
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
    process = await parity.cli(
        "kicad_tooling.electrical",
        "--project",
        PROJECT,
        "--native-summary",
        summary_arg,
        "--output",
        "build/electrical/rs485-fault",
    )
    assert process.returncode == 1, process.stderr + process.stdout
    cli_fault = ElectricalAnalysisReport.model_validate_json(process.stdout)
    async with Client(create_server(parity.mcp_root, allow_checks=True), mode="legacy") as client:
        result = await client.call_tool(
            "analyze_electrical",
            {"project_id": PROJECT, "view_id": "rs485-fault", "native_summary": summary_arg},
        )
    assert not result.is_error, result.content
    mcp_fault = ElectricalAnalysisReport.model_validate_json(json.dumps(result.structured_content))
    assert cli_fault.checks == mcp_fault.checks
    fault_checks = {row.id: row for row in cli_fault.checks}
    assert fault_checks["rs485/fieldbus/pair/shared/termination/local-end"].status == "FAIL"


def test_rs485_contract_matches_cli_and_mcp_for_pass_and_fault(
    parity: ElectricalParityHarness,
) -> None:
    asyncio.run(_run_rs485_contract_matches_cli_and_mcp_for_pass_and_fault(parity))
