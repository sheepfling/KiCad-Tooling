"""CLI/MCP parity for authored power-source and load membership."""

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
from tests.electrical_power_connectivity_support import (
    power_connectivity_netlist,
    power_connectivity_requirement,
)
from tests.electrical_simulation_support import (
    ISLAND,
    PROJECT,
)

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


async def _run_power_connectivity_matches_cli_and_mcp_for_pass_and_fault(
    parity: ElectricalParityHarness,
) -> None:
    parity.configured()
    requirement = power_connectivity_requirement()
    observed = power_connectivity_netlist()
    for root in (parity.root, parity.mcp_root):
        contract_path = root / ISLAND / "tests/electrical.json"
        contract = read_model(contract_path, ElectricalAnalysisContract)
        write_model(contract_path, contract.model_copy(update={"power_connectivity": requirement}))
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
        "build/electrical/power-connectivity-pass",
    )
    assert process.returncode == 0, process.stderr + process.stdout
    cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
    async with Client(create_server(parity.mcp_root, allow_checks=True), mode="legacy") as client:
        result = await client.call_tool(
            "analyze_electrical",
            {
                "project_id": PROJECT,
                "view_id": "power-connectivity-pass",
                "native_summary": summary_arg,
            },
        )
    assert not result.is_error, result.content
    mcp_report = ElectricalAnalysisReport.model_validate_json(json.dumps(result.structured_content))
    assert cli_report.checks == mcp_report.checks
    checks = {row.id: row for row in cli_report.checks}
    assert checks["power-connectivity/supply/source/approved-inputs"].status == "PASS"
    assert checks["power-connectivity/supply/load/load"].status == "PASS"

    faulty = contract_netlist_xml(power_connectivity_netlist(fault="load-wrong-net"))
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
    failed = await parity.cli(
        "kicad_tooling.electrical",
        "--project",
        PROJECT,
        "--native-summary",
        summary_arg,
        "--output",
        "build/electrical/power-connectivity-fault",
    )
    assert failed.returncode == 1, failed.stderr + failed.stdout
    cli_failed = ElectricalAnalysisReport.model_validate_json(failed.stdout)
    async with Client(create_server(parity.mcp_root, allow_checks=True), mode="legacy") as client:
        result = await client.call_tool(
            "analyze_electrical",
            {
                "project_id": PROJECT,
                "view_id": "power-connectivity-fault",
                "native_summary": summary_arg,
            },
        )
    assert not result.is_error, result.content
    mcp_failed = ElectricalAnalysisReport.model_validate_json(json.dumps(result.structured_content))
    assert cli_failed.checks == mcp_failed.checks
    fault_checks = {row.id: row for row in cli_failed.checks}
    assert fault_checks["power-connectivity/supply/load/load"].status == "FAIL"


def test_power_connectivity_matches_cli_and_mcp_for_pass_and_fault(
    parity: ElectricalParityHarness,
) -> None:
    asyncio.run(_run_power_connectivity_matches_cli_and_mcp_for_pass_and_fault(parity))
