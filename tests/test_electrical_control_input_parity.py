"""CLI/MCP parity for authored control-input and test-access contracts."""

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
    ExcludedTestAccess,
    RequiredTestAccess,
    ValidationSummary,
)
from kicad_tooling.hwrepo.models import (
    TestAccessAnalysis as AccessAnalysis,
)
from kicad_tooling.hwrepo.models import (
    TestAccessEndpointRequirement as AccessEndpointRequirement,
)
from tests.electrical_parity_support import (
    ElectricalParityHarness,
    contract_netlist_xml,
    parity_harness,  # noqa: F401
)
from tests.electrical_simulation_support import ISLAND, NA, PROJECT
from tests.test_control_inputs import control_netlist, control_requirement

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.interface_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


async def _run_control_input_requirements_match_cli_mcp_and_retained_evidence(
    parity: ElectricalParityHarness,
) -> None:
    parity.configured()
    requirement = control_requirement()
    access_requirement = AccessAnalysis(
        basis="Synthetic service procedure and interface pin review",
        pcb_accessibility=NA,
        decisions=(
            RequiredTestAccess(
                mode="required",
                id="reset-access",
                basis="Factory service requires access to reset",
                net="RESET_N",
                endpoints=(
                    AccessEndpointRequirement(
                        kind="programming_connector",
                        reference="J1",
                        symbol="Synthetic:DB9",
                        footprint="Connector:Dsub-9_Male",
                        pin="J1.9",
                        electrical_type="passive",
                    ),
                ),
            ),
            ExcludedTestAccess(
                mode="not_required",
                id="hazardous-node",
                basis="Synthetic safety review",
                net="HV_OUT",
                reason="The hazardous synthetic node is excluded from service probing.",
            ),
        ),
    )
    observed = control_netlist()
    for root in (parity.root, parity.mcp_root):
        contract_path = root / ISLAND / "tests/electrical.json"
        contract = read_model(contract_path, ElectricalAnalysisContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={"control_inputs": requirement, "test_access": access_requirement}
            ),
        )
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
        "build/electrical/control-inputs-pass",
    )
    assert process.returncode == 0, process.stderr + process.stdout
    cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
    async with Client(create_server(parity.mcp_root, allow_checks=True), mode="legacy") as client:
        result = await client.call_tool(
            "analyze_electrical",
            {
                "project_id": PROJECT,
                "view_id": "control-inputs-pass",
                "native_summary": summary_arg,
            },
        )
    assert not result.is_error, result.content
    mcp_report = ElectricalAnalysisReport.model_validate_json(json.dumps(result.structured_content))
    assert cli_report.checks == mcp_report.checks
    checks = {row.id: row for row in cli_report.checks}
    assert checks["control-inputs/main-reset/endpoints"].status == "PASS"
    assert checks["control-inputs/main-reset/drivers"].status == "PASS"
    assert checks["control-inputs/main-reset/bias"].status == "PASS"
    assert checks["test-access/schematic/reset-access"].status == "PASS"
    assert checks["test-access/schematic/hazardous-node"].status == "NOT_APPLICABLE"

    faulty = contract_netlist_xml(control_netlist(fault="extra-output"))
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
        "build/electrical/control-inputs-fault",
    )
    assert failed.returncode == 1, failed.stderr + failed.stdout
    cli_failed = ElectricalAnalysisReport.model_validate_json(failed.stdout)
    async with Client(create_server(parity.mcp_root, allow_checks=True), mode="legacy") as client:
        result = await client.call_tool(
            "analyze_electrical",
            {
                "project_id": PROJECT,
                "view_id": "control-inputs-fault",
                "native_summary": summary_arg,
            },
        )
    assert not result.is_error, result.content
    mcp_failed = ElectricalAnalysisReport.model_validate_json(json.dumps(result.structured_content))
    assert cli_failed.checks == mcp_failed.checks
    fault_checks = {row.id: row for row in cli_failed.checks}
    assert fault_checks["control-inputs/main-reset/drivers"].status == "FAIL"


def test_control_input_requirements_match_cli_mcp_and_retained_evidence(
    parity: ElectricalParityHarness,
) -> None:
    asyncio.run(_run_control_input_requirements_match_cli_mcp_and_retained_evidence(parity))
