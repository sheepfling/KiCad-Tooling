"""Design-lint CLI/MCP parity cases: design lint mcp parity stm32."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
]

from pathlib import Path

from mcp import Client

from kicad_tooling.hwrepo.contracts import (
    parse_model_text,
    read_model,
    write_model,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    ProjectTestContract,
    Stm32CubeMxPinMap,
    Stm32PinExclusion,
    Stm32PinRequirement,
    ValidationSummary,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)


class _DesignLintMcpParityStm32Cases(McpParityHarness):
    async def _case_test_stm32_cube_mx_pin_map_parity(self) -> None:
        """Compare one valid pin map and one firmware pin drift through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            "<export><components>"
            '<comp ref="U1"><value>STM32F103C8T6</value>'
            "<footprint>Synthetic:LQFP-48</footprint>"
            '<libsource lib="Synthetic" part="STM32F103"/></comp>'
            '</components><libparts><libpart lib="Synthetic" part="STM32F103"><pins>'
            '<pin num="1" name="PA0" type="bidirectional"/>'
            '<pin num="2" name="PB6" type="bidirectional"/>'
            '<pin num="3" name="PB7" type="bidirectional"/>'
            '<pin num="34" name="PA13" type="bidirectional"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="USER_BUTTON"><node ref="U1" pin="1"/></net>'
            '<net name="I2C_SCL"><node ref="U1" pin="2"/></net>'
            '<net name="I2C_SDA"><node ref="U1" pin="3"/></net>'
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

        ioc_path = self.root / "firmware/controller.ioc"
        ioc_path.parent.mkdir(parents=True)
        ioc_path.write_bytes(
            (Path(__file__).parent / "fixtures/design_lint/stm32-pin-map/valid.ioc").read_bytes()
        )
        pin_map = Stm32CubeMxPinMap(
            id="main-mcu",
            basis="Synthetic reviewed STM32F103 package pin table",
            reference="U1",
            expected_symbol="Synthetic:STM32F103",
            expected_part="STM32F103C8T6",
            ioc_path="firmware/controller.ioc",
            package_pins=("PA0", "PB6", "PB7", "PA13"),
            pins=(
                Stm32PinRequirement(
                    port_pin="PA0",
                    symbol_pin="1",
                    expected_net="USER_BUTTON",
                    accepted_ioc_signals=("GPIO_Input",),
                    accepted_ioc_gpio_labels=("BUTTON",),
                ),
                Stm32PinRequirement(
                    port_pin="PB6",
                    symbol_pin="2",
                    expected_net="I2C_SCL",
                    accepted_ioc_signals=("I2C1_SCL",),
                    accepted_ioc_gpio_labels=("SCL",),
                ),
                Stm32PinRequirement(
                    port_pin="PB7",
                    symbol_pin="3",
                    expected_net="I2C_SDA",
                    accepted_ioc_signals=("I2C1_SDA",),
                    accepted_ioc_gpio_labels=("SDA",),
                ),
            ),
            exclusions=(
                Stm32PinExclusion(
                    port_pin="PA13", reason="Reserved for the synthetic SWD debug interface"
                ),
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={"design_lint": DesignLintPolicy(stm32_pin_maps=(pin_map,))}
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(
                    process.returncode, 0 if cli.status == "PASS" else 1, process.stderr
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
                return mcp

            valid = await compare()
            self.assertEqual(valid.stm32_pin_map_coverage.status, "COMPLETE")
            self.assertEqual(valid.stm32_pin_map_coverage.mismatches, ())
            self.assertEqual(valid.source_hashes["firmware/controller.ioc"], digest(ioc_path))

            ioc_path.write_text(
                ioc_path.read_text(encoding="utf-8").replace(
                    "PA0.Signal=GPIO_Input", "PA0.Signal=GPIO_Output"
                ),
                encoding="utf-8",
            )
            drifted = await compare()
            mismatch = drifted.stm32_pin_map_coverage.mismatches[0]
            self.assertEqual(mismatch.port_pin, "PA0")
            self.assertNotEqual(valid.source_hashes["firmware/controller.ioc"], mismatch.ioc_sha256)
            finding = next(
                item for item in drifted.findings if item.rule_id == "mcu.stm32_cubemx_pin_map"
            )
            self.assertEqual(finding.evidence["ioc_sha256"], (mismatch.ioc_sha256,))


def test_stm32_cube_mx_pin_map_parity() -> None:
    run_mcp_parity(_DesignLintMcpParityStm32Cases, "_case_test_stm32_cube_mx_pin_map_parity")
