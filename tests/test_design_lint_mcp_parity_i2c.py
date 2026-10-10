"""Design-lint CLI/MCP parity cases: design lint mcp parity i2c."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
]

from mcp import Client

from kicad_tooling.hwrepo.contracts import (
    read_model,
    write_model,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    AnalysisPending,
    DesignLintPolicy,
    DesignLintReport,
    ElectricalAnalysisContract,
    I2cAddressBitRequirement,
    I2cAddressMap,
    I2cAddressSegmentRequirement,
    I2cPullupAnalysis,
    I2cPullupArrayChannelRequirement,
    I2cPullupArrayRequirement,
    I2cPullupBusRequirement,
    I2cPullupLineRequirement,
    I2cResponderAddressRequirement,
    ProjectManifest,
    ProjectTestContract,
    ValidationSummary,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)


class _DesignLintMcpParityI2CCases(McpParityHarness):
    async def _case_test_i2c_mapped_array_hint_resolution_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        checks_path = self.island / manifest.checks
        project_test = read_model(checks_path, ProjectTestContract)
        electrical_relative = "tests/i2c-electrical.json"
        electrical_path = self.island / electrical_relative
        electrical_path.parent.mkdir(parents=True, exist_ok=True)
        pullup_spec = I2cPullupAnalysis(
            basis="Synthetic mapped resistor-array requirement",
            buses=(
                I2cPullupBusRequirement(
                    id="main",
                    basis="Synthetic two-wire interface requirement",
                    sda=I2cPullupLineRequirement(
                        net="I2C_SDA",
                        rail="+3V3",
                        minimum_ohms=1_000,
                        maximum_ohms=100_000,
                    ),
                    scl=I2cPullupLineRequirement(
                        net="I2C_SCL",
                        rail="+3V3",
                        minimum_ohms=1_000,
                        maximum_ohms=100_000,
                    ),
                ),
            ),
            arrays=(
                I2cPullupArrayRequirement(
                    reference="RN1",
                    expected_symbol="Synthetic:ResistorArray",
                    expected_footprint="Synthetic:RA4",
                    expected_value="4x4.7k",
                    basis="Synthetic array datasheet pin map",
                    channels=(
                        I2cPullupArrayChannelRequirement(
                            id="sda",
                            signal_pin="RN1.1",
                            rail_pin="RN1.2",
                            signal_net="I2C_SDA",
                            rail_net="+3V3",
                            resistance_ohms=4_700,
                            basis="Synthetic channel 1 map",
                        ),
                        I2cPullupArrayChannelRequirement(
                            id="scl",
                            signal_pin="RN1.3",
                            rail_pin="RN1.4",
                            signal_net="I2C_SCL",
                            rail_net="+3V3",
                            resistance_ohms=4_700,
                            basis="Synthetic channel 2 map",
                        ),
                    ),
                ),
            ),
        )
        write_model(
            checks_path,
            project_test.model_copy(update={"electrical": electrical_relative}),
        )
        write_model(
            electrical_path,
            ElectricalAnalysisContract(
                project_id="controller",
                ngspice_version="not run by synthetic parity fixture",
                grounding=AnalysisPending(reason="Synthetic fixture does not exercise grounding."),
                i2c_pullups=pullup_spec,
                power=AnalysisPending(reason="Synthetic fixture does not exercise power budgets."),
                high_frequency=AnalysisPending(
                    reason="Synthetic fixture does not exercise high-frequency analysis."
                ),
            ),
        )
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            "<export><components>"
            '<comp ref="U1"><value>Synthetic two-wire target</value>'
            '<libsource lib="Synthetic" part="I2cTarget"/></comp>'
            '<comp ref="RN1"><value>4x4.7k</value><footprint>Synthetic:RA4</footprint>'
            '<libsource lib="Synthetic" part="ResistorArray"/></comp>'
            "</components><libparts>"
            '<libpart lib="Synthetic" part="I2cTarget"><pins>'
            '<pin num="1" name="SDA" type="passive"/>'
            '<pin num="2" name="SCL" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="ResistorArray"><pins>'
            '<pin num="1" name="1" type="passive"/><pin num="2" name="2" type="passive"/>'
            '<pin num="3" name="3" type="passive"/><pin num="4" name="4" type="passive"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="I2C_SDA"><node ref="U1" pin="1"/><node ref="RN1" pin="1"/></net>'
            '<net name="I2C_SCL"><node ref="U1" pin="2"/><node ref="RN1" pin="3"/></net>'
            '<net name="+3V3"><node ref="RN1" pin="2"/><node ref="RN1" pin="4"/></net>'
            "</nets></export>",
            encoding="utf-8",
        )
        summary = read_model(native, ValidationSummary)
        write_model(
            native,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(netlist),
                    }
                }
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:
            cli = await self.cli(
                "kicad_tooling.design_lint",
                DesignLintReport,
                "--project",
                "controller",
                "--native-summary",
                str(native),
                expected_exit=1,
            )
            mcp = await self.call(
                client,
                "inspect_design_lint",
                DesignLintReport,
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(self.root).as_posix(),
                },
            )
        self.assertEqual(cli, mcp)
        self.assertEqual(mcp.i2c_pullup_heuristic_coverage.status, "COMPLETE")
        self.assertEqual(
            mcp.i2c_pullup_heuristic_coverage.source_path,
            electrical_path.relative_to(self.root).as_posix(),
        )
        self.assertEqual(
            mcp.i2c_pullup_heuristic_coverage.netlist_sha256,
            digest(netlist),
        )
        self.assertNotIn("bus.i2c_missing_pullup", {item.rule_id for item in mcp.findings})

    async def _case_test_i2c_address_map_parity(self) -> None:
        """Compare mapped static-address review through the CLI and MCP surfaces."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            "<export><components>"
            '<comp ref="U1"><value>Synthetic EEPROM</value>'
            '<libsource lib="Synthetic" part="EEPROM"/></comp>'
            '<comp ref="U2"><value>Synthetic EEPROM</value>'
            '<libsource lib="Synthetic" part="EEPROM"/></comp>'
            '<comp ref="U3"><value>Unmapped synthetic EEPROM</value>'
            '<libsource lib="Synthetic" part="EEPROM"/></comp>'
            '<comp ref="R1"><value>4.7k</value><libsource lib="Device" part="R"/></comp>'
            '<comp ref="R2"><value>4.7k</value><libsource lib="Device" part="R"/></comp>'
            "</components><libparts>"
            '<libpart lib="Synthetic" part="EEPROM"><pins>'
            '<pin num="1" name="SDA" type="passive"/>'
            '<pin num="2" name="SCL" type="passive"/>'
            '<pin num="3" name="A0" type="passive"/>'
            "</pins></libpart>"
            '<libpart lib="Device" part="R"><pins>'
            '<pin num="1" name="1" type="passive"/>'
            '<pin num="2" name="2" type="passive"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="I2C_SDA"><node ref="U1" pin="1"/>'
            '<node ref="U2" pin="1"/><node ref="U3" pin="1"/>'
            '<node ref="R1" pin="1"/></net>'
            '<net name="I2C_SCL"><node ref="U1" pin="2"/>'
            '<node ref="U2" pin="2"/><node ref="U3" pin="2"/>'
            '<node ref="R2" pin="1"/></net>'
            '<net name="+3V3"><node ref="U1" pin="3"/>'
            '<node ref="R1" pin="2"/><node ref="R2" pin="2"/></net>'
            '<net name="GND"><node ref="U2" pin="3"/></net>'
            "</nets></export>",
            encoding="utf-8",
        )
        summary = read_model(native, ValidationSummary)
        write_model(
            native,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(netlist),
                    }
                }
            ),
        )

        address_map = I2cAddressMap(
            basis="Synthetic reviewed responder and segment map",
            segments=(
                I2cAddressSegmentRequirement(
                    id="main",
                    sda_net="I2C_SDA",
                    scl_net="I2C_SCL",
                    responders=(
                        I2cResponderAddressRequirement(
                            reference="U1",
                            expected_symbol="Synthetic:EEPROM",
                            sda_pin="U1.1",
                            scl_pin="U1.2",
                            mode="strapped",
                            address=0x50,
                            address_bits=(
                                I2cAddressBitRequirement(
                                    bit=0,
                                    pin="U1.3",
                                    function="A0",
                                    low_net="GND",
                                    high_net="+3V3",
                                ),
                            ),
                            basis="Synthetic expected 7-bit address 0x50",
                        ),
                        I2cResponderAddressRequirement(
                            reference="U2",
                            expected_symbol="Synthetic:EEPROM",
                            sda_pin="U2.1",
                            scl_pin="U2.2",
                            mode="fixed",
                            address=0x51,
                            basis="Synthetic fixed 7-bit address 0x51",
                        ),
                    ),
                ),
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={"design_lint": DesignLintPolicy(i2c_address_map=address_map)}
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:
            cli = await self.cli(
                "kicad_tooling.design_lint",
                DesignLintReport,
                "--project",
                "controller",
                "--native-summary",
                str(native),
                expected_exit=1,
            )
            mcp = await self.call(
                client,
                "inspect_design_lint",
                DesignLintReport,
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(self.root).as_posix(),
                },
            )
        self.assertEqual(cli, mcp)
        self.assertEqual(mcp.status, "REVIEW", mcp.model_dump_json(indent=2))
        self.assertEqual(mcp.i2c_address_coverage.status, "COMPLETE")
        self.assertEqual(mcp.i2c_address_coverage.netlist_sha256, digest(netlist))
        mismatch = [item for item in mcp.findings if item.rule_id == "bus.i2c_address_mismatch"]
        collisions = [item for item in mcp.findings if item.rule_id == "bus.i2c_address_collision"]
        self.assertEqual(len(mismatch), 1)
        self.assertEqual(len(collisions), 1)
        self.assertEqual(mismatch[0].subject, "U1 on main: 0x51")
        self.assertEqual(collisions[0].subject, "main: U1, U2 at 0x51")
        unmapped = [item for item in mcp.findings if item.rule_id == "bus.i2c_unmapped_responder"]
        self.assertEqual(len(unmapped), 1)
        self.assertEqual(unmapped[0].subject, "U3: I2C address-map coverage")


def test_i2c_mapped_array_hint_resolution_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityI2CCases, "_case_test_i2c_mapped_array_hint_resolution_cli_mcp_parity"
    )


def test_i2c_address_map_parity() -> None:
    run_mcp_parity(_DesignLintMcpParityI2CCases, "_case_test_i2c_address_map_parity")
