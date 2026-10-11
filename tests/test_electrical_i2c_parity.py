"""I2C electrical contract checks keep CLI and MCP results in parity."""

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
    I2cPullupAnalysis,
    NetlistContract,
    ValidationSummary,
)
from tests import electrical_i2c_support as i2c_support
from tests.electrical_parity_support import ElectricalParityHarness, contract_netlist_xml
from tests.test_electrical import ISLAND, PROJECT

pytestmark = [
    pytest.mark.template_checkout,
]


@pytest.fixture
def parity():
    harness = ElectricalParityHarness()
    try:
        yield harness
    finally:
        harness.close()


async def _run_i2c_array_pullups_match_cli_and_mcp_for_pass_and_fault(parity) -> None:
    parity.configured()
    requirement = i2c_support.i2c_pullup_array_requirement()

    def install_netlist(observed: NetlistContract) -> None:
        serialized = contract_netlist_xml(observed)
        for root in (parity.root, parity.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(contract_path, contract.model_copy(update={"i2c_pullups": requirement}))
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

    async def analyze_both(
        view_id: str,
    ) -> tuple[ElectricalAnalysisReport, ElectricalAnalysisReport, int]:
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
                {"project_id": PROJECT, "view_id": view_id, "native_summary": summary},
            )
        assert not result.is_error, result.content
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        assert cli_report.checks == mcp_report.checks
        return (cli_report, mcp_report, process.returncode)

    install_netlist(i2c_support.i2c_pullup_array_netlist())
    (cli_pass, _, pass_returncode) = await analyze_both("i2c-array-pass")
    assert pass_returncode == 0
    pass_checks = {item.id: item for item in cli_pass.checks}
    for line in ("sda", "scl"):
        assert pass_checks[f"i2c-pullup/array-bus/{line}"].status == "PASS"
        assert pass_checks[f"i2c-pullup/array-bus/{line}"].observed == 4700
    observed_fault = i2c_support.i2c_pullup_array_netlist()
    components = dict(observed_fault.components)
    components["RN1"] = ComponentContract(value="4x10k", footprint="Synthetic:RA4")
    install_netlist(observed_fault.model_copy(update={"components": components}))
    (cli_fault, _, fault_returncode) = await analyze_both("i2c-array-fault")
    assert fault_returncode == 1
    fault_checks = {item.id: item for item in cli_fault.checks}
    for line in ("sda", "scl"):
        check = fault_checks[f"i2c-pullup/array-bus/{line}"]
        assert check.status == "FAIL"
        assert "RN1 value is 4x10k; expected 4x4.7k" in check.detail


def test_i2c_array_pullups_match_cli_and_mcp_for_pass_and_fault(parity):
    asyncio.run(_run_i2c_array_pullups_match_cli_and_mcp_for_pass_and_fault(parity))


async def _run_i2c_voltage_compatibility_matches_cli_and_mcp_for_pass_and_fault(parity) -> None:
    parity.configured()

    def install_netlist(observed: NetlistContract, requirement: I2cPullupAnalysis) -> None:
        serialized = contract_netlist_xml(observed)
        for root in (parity.root, parity.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(contract_path, contract.model_copy(update={"i2c_pullups": requirement}))
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

    async def analyze_both(
        view_id: str,
    ) -> tuple[ElectricalAnalysisReport, ElectricalAnalysisReport, int]:
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
                {"project_id": PROJECT, "view_id": view_id, "native_summary": summary},
            )
        assert not result.is_error, result.content
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        assert cli_report.checks == mcp_report.checks
        return (cli_report, mcp_report, process.returncode)

    observed = i2c_support.i2c_series_pullup_netlist()
    install_netlist(observed, i2c_support.i2c_pullup_voltage_requirement())
    (pass_report, _, pass_returncode) = await analyze_both("i2c-voltage-pass")
    assert pass_returncode == 0
    assert f"{ISLAND}/tests/electrical.json" in pass_report.input_sha256
    pass_checks = {item.id: item for item in pass_report.checks}
    for line in ("sda", "scl"):
        check = pass_checks[f"i2c-pullup/series-bus/{line}/voltage-compatibility"]
        assert check.status == "PASS"
        assert check.observed == 3.3
    install_netlist(
        observed, i2c_support.i2c_pullup_voltage_requirement(maximum_input_voltage_v=3.2)
    )
    (fault_report, _, fault_returncode) = await analyze_both("i2c-voltage-fault")
    assert fault_returncode == 1
    fault_checks = {item.id: item for item in fault_report.checks}
    for pin, line in (("U1.1", "sda"), ("U1.2", "scl")):
        check = fault_checks[f"i2c-pullup/series-bus/{line}/voltage-compatibility"]
        assert check.status == "FAIL"
        assert f"{pin} maximum bus voltage 3.2 V" in check.detail


def test_i2c_voltage_compatibility_matches_cli_and_mcp_for_pass_and_fault(parity):
    asyncio.run(_run_i2c_voltage_compatibility_matches_cli_and_mcp_for_pass_and_fault(parity))


async def _run_i2c_pullup_electrical_window_matches_cli_and_mcp(parity) -> None:
    parity.configured()

    def install_netlist(observed: NetlistContract, requirement: I2cPullupAnalysis) -> None:
        serialized = contract_netlist_xml(observed)
        for root in (parity.root, parity.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(contract_path, contract.model_copy(update={"i2c_pullups": requirement}))
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
                {"project_id": PROJECT, "view_id": view_id, "native_summary": summary},
            )
        assert not result.is_error, result.content
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        assert cli_report.checks == mcp_report.checks
        return (cli_report, process.returncode)

    observed = i2c_support.i2c_series_pullup_netlist()
    install_netlist(observed, i2c_support.i2c_pullup_window_requirement())
    (pass_report, pass_returncode) = await analyze_both("i2c-window-pass")
    assert pass_returncode == 0
    pass_checks = {item.id: item for item in pass_report.checks}
    for line in ("sda", "scl"):
        for bound in ("minimum-sink-resistance", "maximum-rise-resistance"):
            assert (
                pass_checks[f"i2c-pullup/series-bus/{line}/electrical-window/{bound}"].status
                == "PASS"
            )
    install_netlist(
        observed, i2c_support.i2c_pullup_window_requirement(maximum_bus_capacitance_pf=100.0)
    )
    (fault_report, fault_returncode) = await analyze_both("i2c-window-fault")
    assert fault_returncode == 1
    fault_checks = {item.id: item for item in fault_report.checks}
    for line in ("sda", "scl"):
        check = fault_checks[
            f"i2c-pullup/series-bus/{line}/electrical-window/maximum-rise-resistance"
        ]
        assert check.status == "FAIL"
        assert "3540.66Ω" in check.detail


def test_i2c_pullup_electrical_window_matches_cli_and_mcp(parity):
    asyncio.run(_run_i2c_pullup_electrical_window_matches_cli_and_mcp(parity))


async def _run_i2c_series_pullups_match_cli_and_mcp_for_pass_and_fault(parity) -> None:
    parity.configured()
    requirement = i2c_support.i2c_series_pullup_requirement()

    def install_netlist(observed: NetlistContract) -> None:
        serialized = contract_netlist_xml(observed)
        for root in (parity.root, parity.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(contract_path, contract.model_copy(update={"i2c_pullups": requirement}))
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
                {"project_id": PROJECT, "view_id": view_id, "native_summary": summary},
            )
        assert not result.is_error, result.content
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        assert cli_report.checks == mcp_report.checks
        return (cli_report, process.returncode)

    install_netlist(i2c_support.i2c_series_pullup_netlist())
    (passed, pass_returncode) = await analyze_both("i2c-series-pass")
    assert pass_returncode == 0
    pass_checks = {item.id: item for item in passed.checks}
    assert pass_checks["i2c-pullup/series-bus/sda/series/sda-chain"].status == "PASS"
    assert pass_checks["i2c-pullup/series-bus/sda"].observed == 4700
    install_netlist(i2c_support.i2c_series_pullup_netlist(first_value="2k"))
    (fault, fault_returncode) = await analyze_both("i2c-series-fault")
    assert fault_returncode == 1
    fault_checks = {item.id: item for item in fault.checks}
    assert fault_checks["i2c-pullup/series-bus/sda/series/sda-chain"].status == "FAIL"
    assert fault_checks["i2c-pullup/series-bus/sda"].status == "FAIL"


def test_i2c_series_pullups_match_cli_and_mcp_for_pass_and_fault(parity):
    asyncio.run(_run_i2c_series_pullups_match_cli_and_mcp_for_pass_and_fault(parity))
