"""CLI/MCP parity for authored connector pin relationships."""

from __future__ import annotations

import asyncio
import json

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    GroundDomain,
    NetlistContract,
    PinConnectivityAnalysis,
    PinRelationshipRule,
    ValidationSummary,
)
from tests.electrical_parity_support import parity_harness  # noqa: F401
from tests.electrical_simulation_support import ISLAND, PROJECT

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


async def _run_connector_pin_relationships_match_cli_and_mcp(parity) -> None:
    parity.configured(grounding=True)
    for root in (parity.root, parity.mcp_root):
        contract_path = root / ISLAND / "tests/electrical.json"
        contract = read_model(contract_path, ElectricalAnalysisContract)
        grounding = contract.grounding
        assert grounding.mode == "required"
        grounding = grounding.model_copy(
            update={
                "domains": (
                    *contract.grounding.domains,
                    GroundDomain(net="GND", pins=("J1.9", "J2.9", "J3.9")),
                ),
                "exempt_components": {
                    **contract.grounding.exempt_components,
                    "J4": "Synthetic connector fixture has no reviewed ground pins",
                },
            }
        )
        pin_connectivity = PinConnectivityAnalysis(
            basis="Synthetic approved connector power pinout",
            rules=(
                PinRelationshipRule(
                    id="port-power",
                    basis="Three ports share the same supply rail",
                    topology="common_net",
                    pins=("J1.1", "J2.1", "J3.1"),
                    net="+5V",
                ),
                PinRelationshipRule(
                    id="unused-pin",
                    basis="Synthetic assembly leaves this optional connector pin unused",
                    topology="unconnected",
                    pins=("J4.2",),
                ),
            ),
        )
        write_model(
            contract_path,
            contract.model_copy(
                update={"grounding": grounding, "pin_connectivity": pin_connectivity}
            ),
        )
        native = root / "build/native/controller"
        netlist = native / "netlist.xml"
        observed = netlist.read_text(encoding="utf-8")
        observed = observed.replace(
            "</components>",
            '<comp ref="J1"><value>Test</value></comp>'
            '<comp ref="J2"><value>Test</value></comp>'
            '<comp ref="J3"><value>Test</value></comp>'
            '<comp ref="J4"><value>Test</value></comp></components>',
        ).replace(
            "</nets>",
            '<net name="GND"><node ref="J1" pin="9"/><node ref="J2" pin="9"/>'
            '<node ref="J3" pin="9"/></net>'
            '<net name="USB1_GND"><node ref="J1" pin="4"/></net>'
            '<net name="USB2_GND"><node ref="J2" pin="4"/></net>'
            '<net name="USB3_GND"><node ref="J3" pin="4"/></net>'
            '<net name="+5V"><node ref="J1" pin="1"/>'
            '<node ref="J2" pin="1"/></net>'
            '<net name="PORT3_PWR"><node ref="J3" pin="1"/></net></nets>',
        )
        netlist.write_text(observed, encoding="utf-8")
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
    summary = "build/native/controller/summary.json"
    process = await parity.cli(
        "kicad_tooling.electrical",
        "--project",
        PROJECT,
        "--native-summary",
        summary,
        "--output",
        "build/electrical/split-returns",
    )
    assert process.returncode == 1, process.stderr + process.stdout
    cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
    async with Client(create_server(parity.mcp_root, allow_checks=True), mode="legacy") as client:
        result = await client.call_tool(
            "analyze_electrical",
            {
                "project_id": PROJECT,
                "view_id": "split-returns",
                "native_summary": summary,
            },
        )
    assert not result.is_error, result.content
    mcp_report = ElectricalAnalysisReport.model_validate_json(json.dumps(result.structured_content))
    assert cli_report.checks == mcp_report.checks
    for report in (cli_report, mcp_report):
        assert report.status == "FAIL"
        checks = {row.id: row for row in report.checks}
        assert checks["grounding/GND"].status == "PASS"
        assert checks["grounding/component-coverage"].status == "PASS"
        assert checks["grounding/return-net-review"].status == "FAIL"
        assert "J1.4" in checks["grounding/return-net-review"].detail
        assert "USB3_GND" in checks["grounding/return-net-review"].detail
        assert checks["pin-connectivity/port-power"].status == "FAIL"
        assert "J3.1" in checks["pin-connectivity/port-power"].detail
        unused_pin = checks["pin-connectivity/unused-pin"]
        assert unused_pin.status == "FAIL"
        assert "missing symbol pin inventory=['J4']" in unused_pin.detail


def test_connector_pin_relationships_match_cli_and_mcp_analysis(parity) -> None:
    asyncio.run(_run_connector_pin_relationships_match_cli_and_mcp(parity))


async def _run_required_pin_assignment_matches_cli_and_mcp(parity) -> None:

    parity.configured()
    requirement = PinConnectivityAnalysis(
        basis="Approved synthetic connector pinout requires both power contacts to be wired",
        rules=(
            PinRelationshipRule(
                id="assigned-power-contacts",
                basis="Each reviewed contact must have one net assignment",
                topology="assigned",
                pins=("J1.1", "J2.1"),
            ),
        ),
    )
    observed = NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic power port", footprint="")
            for reference in ("J1", "J2")
        },
        nets={"PORT1_PWR": ("J1.1",)},
        component_symbols={"J1": "Synthetic:Port", "J2": "Synthetic:Port"},
        component_pin_numbers={"J1": ("1",), "J2": ("1",)},
    )
    parity.install_netlist_contract(observed, {"pin_connectivity": requirement})
    cli_report, mcp_report, returncode = await parity.analyze_electrical("required-pin-assignment")

    assert returncode == 1
    assert cli_report.checks == mcp_report.checks
    for report in (cli_report, mcp_report):
        check = next(
            item for item in report.checks if item.id == "pin-connectivity/assigned-power-contacts"
        )
        assert check.status == "FAIL"
        assert "J2.1" in check.detail


def test_required_pin_assignment_matches_cli_and_mcp(parity) -> None:
    asyncio.run(_run_required_pin_assignment_matches_cli_and_mcp(parity))
