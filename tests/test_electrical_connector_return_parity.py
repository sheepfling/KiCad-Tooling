"""CLI/MCP parity for reviewed connector-return requirements."""

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
    GroundDomain,
    GroundingAnalysis,
    ValidationSummary,
)
from tests.design_lint_fixtures.connector_return_cases import return_case_contracts
from tests.electrical_parity_support import contract_netlist_xml, parity_harness  # noqa: F401
from tests.test_electrical import ISLAND, PROJECT

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.return_path_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


async def _run_db9_grounding_requirement_matrix(parity) -> None:
    parity.configured()
    netlists = return_case_contracts()
    all_returns = tuple(f"J{index}.{pin}" for index in range(1, 5) for pin in (7, 9))
    requirements = {
        "common": GroundingAnalysis(
            basis="Synthetic approved DB9 pinout requires all return contacts on one domain",
            domains=(GroundDomain(net="COMMON_RETURN", pins=all_returns),),
        ),
        "isolated": GroundingAnalysis(
            basis="Synthetic approved DB9 pinout requires one isolated domain per connector",
            domains=tuple(
                GroundDomain(net=f"RETURN_PORT_{index}", pins=(f"J{index}.7", f"J{index}.9"))
                for index in range(1, 5)
            ),
        ),
    }
    cases = (
        ("split-against-common", True, "common", "FAIL"),
        ("common-against-common", False, "common", "PASS"),
        ("split-against-isolated", True, "isolated", "PASS"),
        ("common-against-isolated", False, "isolated", "FAIL"),
    )

    for case_id, isolated_returns, requirement_id, expected_status in cases:
        observed = netlists["four-db9-fault" if isolated_returns else "four-db9-control"]
        serialized = contract_netlist_xml(observed)
        for root in (parity.root, parity.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(
                contract_path,
                contract.model_copy(update={"grounding": requirements[requirement_id]}),
            )
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(serialized, encoding="utf-8")
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
            f"build/electrical/db9-{case_id}",
        )
        expected_returncode = 0 if expected_status == "PASS" else 1
        assert process.returncode == expected_returncode, process.stderr + process.stdout
        cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(
            create_server(parity.mcp_root, allow_checks=True), mode="legacy"
        ) as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": f"db9-{case_id}",
                    "native_summary": summary_arg,
                },
            )
        assert not result.is_error, result.content
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        assert cli_report.checks == mcp_report.checks
        for report in (cli_report, mcp_report):
            assert report.status == expected_status
            checks = {item.id: item for item in report.checks}
            assert checks["grounding/component-coverage"].status == "PASS"
            if requirement_id == "common":
                assert checks["grounding/COMMON_RETURN"].status == expected_status
            else:
                for index in range(1, 5):
                    assert checks[f"grounding/RETURN_PORT_{index}"].status == expected_status
            if isolated_returns:
                review_status = "FAIL" if requirement_id == "common" else "PASS"
                assert checks["grounding/return-net-review"].status == review_status


def test_db9_grounding_requirement_matrix_matches_cli_and_mcp(parity) -> None:
    asyncio.run(_run_db9_grounding_requirement_matrix(parity))
