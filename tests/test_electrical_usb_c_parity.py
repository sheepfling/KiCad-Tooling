"""USB-C electrical contract parity checks for the CLI and MCP surfaces."""

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
    NetlistContract,
    ValidationSummary,
)
from tests.electrical_parity_support import contract_netlist_xml, parity_harness  # noqa: F401
from tests.electrical_usb_c_support import usb_c_netlist, usb_c_requirement
from tests.test_electrical import ISLAND, PROJECT

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


async def _run_vbus_path_parity(parity) -> None:
    parity.configured()
    requirement = usb_c_requirement(vbus_path=True)

    def install_netlist(observed: NetlistContract) -> None:
        serialized = contract_netlist_xml(observed)
        for root in (parity.root, parity.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(contract_path, contract.model_copy(update={"usb_c": requirement}))
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

    async def analyze_both(view_id: str) -> tuple[ElectricalAnalysisReport, int]:
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
        async with Client(
            create_server(parity.mcp_root, allow_checks=True), mode="legacy"
        ) as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": view_id,
                    "native_summary": summary,
                },
            )
        assert not result.is_error, result.content
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        assert cli_report.checks == mcp_report.checks
        return cli_report, process.returncode

    install_netlist(usb_c_netlist(vbus_path=True))
    passed, pass_returncode = await analyze_both("usb-c-vbus-path-pass")
    assert pass_returncode == 0
    pass_checks = {item.id: item for item in passed.checks}
    assert pass_checks["usb-c/host-port/vbus-path/input-path"].status == "PASS"

    observed_fault = usb_c_netlist(vbus_path=True)
    nets = {
        net: tuple(pin for pin in pins if pin != "U3.3")
        for net, pins in observed_fault.nets.items()
    }
    nets["VBUS_WRONG"] = ("U3.3",)
    install_netlist(observed_fault.model_copy(update={"nets": nets}))
    fault, fault_returncode = await analyze_both("usb-c-vbus-path-fault")
    assert fault_returncode == 1
    fault_checks = {item.id: item for item in fault.checks}
    path_check = fault_checks["usb-c/host-port/vbus-path/input-path"]
    assert path_check.status == "FAIL"
    assert "U3.3" in path_check.detail


def test_usb_c_vbus_path_matches_cli_and_mcp_for_pass_and_fault(parity) -> None:
    asyncio.run(_run_vbus_path_parity(parity))
