"""Design-lint CLI/MCP parity cases: design lint mcp parity power input."""

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
    ComponentIdentity,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    ProjectManifest,
    ProjectTestContract,
    ValidationSummary,
)
from tests.design_lint_fixtures.power_input_paths import RULE_ID as POWER_INPUT_SOURCE_PATH_RULE_ID
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)


class _DesignLintMcpParityPowerInputCases(McpParityHarness):
    async def _case_test_power_input_source_path_heuristic_cli_mcp_parity(self) -> None:
        """Compare source-path controls and faults through both public surfaces."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(
            *,
            wrong_rail: bool,
            unrecognized_source: bool = False,
            jumper_symbol: str | None = None,
            jumper_pin_numbers: tuple[str, ...] = ("1", "2"),
            jumper_pin_functions: tuple[str, ...] = ("A", "B"),
            jumper_source_pin: str = "1",
            jumper_load_pin: str = "2",
        ) -> None:
            path_reference = "JP1" if jumper_symbol else "FB1"
            if jumper_symbol:
                input_side = '<net name="GND"><node ref="C1" pin="2"/></net>'
                source_side = (
                    f'<net name="VIN"><node ref="U1" pin="1"/>'
                    f'<node ref="JP1" pin="{jumper_source_pin}"/></net>'
                )
                source_pin_type = "power_out"
                load_pin = jumper_load_pin
                unused_pin_nets = "".join(
                    f'<net name="JP_UNUSED_{number}"><node ref="JP1" pin="{number}"/></net>'
                    for number in jumper_pin_numbers
                    if number not in {jumper_source_pin, jumper_load_pin}
                )
            elif unrecognized_source:
                input_side = '<net name="GND"><node ref="C1" pin="2"/></net>'
                source_side = (
                    f'<net name="AUX_INPUT"><node ref="U1" pin="1"/>'
                    f'<node ref="{path_reference}" pin="1"/></net>'
                )
                source_pin_type = "passive"
                load_pin = "2"
                unused_pin_nets = ""
            elif wrong_rail:
                input_side = f'<net name="GND"><node ref="{path_reference}" pin="1"/>'
                input_side += '<node ref="C1" pin="2"/></net>'
                source_side = '<net name="VIN"><node ref="U1" pin="1"/></net>'
                source_pin_type = "power_out"
                load_pin = "2"
                unused_pin_nets = ""
            else:
                input_side = '<net name="GND"><node ref="C1" pin="2"/></net>'
                source_side = (
                    f'<net name="VIN"><node ref="U1" pin="1"/>'
                    f'<node ref="{path_reference}" pin="1"/></net>'
                )
                source_pin_type = "power_out"
                load_pin = "2"
                unused_pin_nets = ""
            path_component = (
                f'<comp ref="JP1"><value>Synthetic jumper</value>'
                "<footprint>Synthetic:0603</footprint>"
                f'<libsource lib="Jumper" part="{jumper_symbol}"/></comp>'
                if jumper_symbol
                else '<comp ref="FB1"><value>Ferrite bead</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="FerriteBead"/></comp>'
            )
            if jumper_symbol:
                path_libpart = (
                    f'<libpart lib="Jumper" part="{jumper_symbol}"><pins>'
                    + "".join(
                        f'<pin num="{number}" name="{function}" type="passive"/>'
                        for number, function in zip(jumper_pin_numbers, jumper_pin_functions)
                    )
                    + "</pins></libpart>"
                )
            else:
                path_libpart = (
                    '<libpart lib="Device" part="FerriteBead"><pins>'
                    '<pin num="1" name="1" type="passive"/>'
                    '<pin num="2" name="2" type="passive"/>'
                    "</pins></libpart>"
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>Synthetic source</value>'
                "<footprint>Synthetic:PowerSource</footprint>"
                '<libsource lib="Synthetic" part="PowerSource"/></comp>'
                f"{path_component}"
                '<comp ref="U2"><value>Synthetic load</value>'
                "<footprint>Synthetic:PowerLoad</footprint>"
                '<libsource lib="Synthetic" part="PowerLoad"/></comp>'
                '<comp ref="C1"><value>100nF</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="C"/></comp>'
                "</components><libparts>"
                '<libpart lib="Synthetic" part="PowerSource"><pins>'
                f'<pin num="1" name="VOUT" type="{source_pin_type}"/>'
                "</pins></libpart>"
                f"{path_libpart}"
                '<libpart lib="Synthetic" part="PowerLoad"><pins>'
                '<pin num="1" name="VIN" type="power_in"/>'
                "</pins></libpart>"
                '<libpart lib="Device" part="C"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                f"{source_side}"
                f'<net name="VLOAD"><node ref="{path_reference}" pin="{load_pin}"/>'
                '<node ref="U2" pin="1"/><node ref="C1" pin="1"/></net>'
                f"{input_side}{unused_pin_nets}</nets></export>",
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

        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "component_identity": ComponentIdentity(required=False, part_ids=()),
                    "interfaces": (),
                    "connector_reviews": (),
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic parity case has no external connector in its fixture"
                    ),
                }
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(update={"design_lint": DesignLintPolicy()}),
        )

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(
                *,
                wrong_rail: bool = False,
                unrecognized_source: bool = False,
                jumper_symbol: str | None = None,
                jumper_pin_numbers: tuple[str, ...] = ("1", "2"),
                jumper_pin_functions: tuple[str, ...] = ("A", "B"),
                jumper_source_pin: str = "1",
                jumper_load_pin: str = "2",
            ) -> DesignLintReport:
                write_netlist(
                    wrong_rail=wrong_rail,
                    unrecognized_source=unrecognized_source,
                    jumper_symbol=jumper_symbol,
                    jumper_pin_numbers=jumper_pin_numbers,
                    jumper_pin_functions=jumper_pin_functions,
                    jumper_source_pin=jumper_source_pin,
                    jumper_load_pin=jumper_load_pin,
                )
                exit_code = int(
                    wrong_rail
                    or unrecognized_source
                    or jumper_symbol == "SolderJumper_2_Open"
                    or (jumper_symbol == "SolderJumper_3_Bridged12" and jumper_load_pin == "3")
                )
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=exit_code,
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

            control = await compare(wrong_rail=False)
            self.assertEqual(control.status, "PASS", control.issues)
            self.assertNotIn(
                POWER_INPUT_SOURCE_PATH_RULE_ID,
                {item.rule_id for item in control.findings},
            )

            fault = await compare(wrong_rail=True)
            self.assertEqual(fault.status, "REVIEW", fault.issues)
            finding = next(
                item for item in fault.findings if item.rule_id == POWER_INPUT_SOURCE_PATH_RULE_ID
            )
            self.assertEqual(finding.subject, "VLOAD: power-input source-path review")

            unknown_source = await compare(unrecognized_source=True)
            self.assertEqual(unknown_source.status, "REVIEW", unknown_source.issues)
            unknown_finding = next(
                item
                for item in unknown_source.findings
                if item.rule_id == POWER_INPUT_SOURCE_PATH_RULE_ID
            )
            self.assertEqual(unknown_finding.evidence["recognized_source_nets"], ())
            self.assertEqual(unknown_finding.evidence["source_anchor_state"], ("not_recognized",))

            bridged_jumper = await compare(jumper_symbol="SolderJumper_2_Bridged")
            self.assertEqual(bridged_jumper.status, "PASS", bridged_jumper.issues)
            self.assertNotIn(
                POWER_INPUT_SOURCE_PATH_RULE_ID,
                {item.rule_id for item in bridged_jumper.findings},
            )

            open_jumper = await compare(jumper_symbol="SolderJumper_2_Open")
            self.assertEqual(open_jumper.status, "REVIEW", open_jumper.issues)
            open_finding = next(
                item
                for item in open_jumper.findings
                if item.rule_id == POWER_INPUT_SOURCE_PATH_RULE_ID
            )
            self.assertEqual(open_finding.subject, "VLOAD: power-input source-path review")

            bridged_three_pin12 = await compare(
                jumper_symbol="SolderJumper_3_Bridged12",
                jumper_pin_numbers=("1", "2", "3"),
                jumper_pin_functions=("A", "C", "B"),
                jumper_source_pin="1",
                jumper_load_pin="2",
            )
            self.assertEqual(bridged_three_pin12.status, "PASS", bridged_three_pin12.issues)
            self.assertNotIn(
                POWER_INPUT_SOURCE_PATH_RULE_ID,
                {item.rule_id for item in bridged_three_pin12.findings},
            )

            bridged_three_pin123 = await compare(
                jumper_symbol="SolderJumper_3_Bridged123",
                jumper_pin_numbers=("1", "2", "3"),
                jumper_pin_functions=("A", "C", "B"),
                jumper_source_pin="1",
                jumper_load_pin="3",
            )
            self.assertEqual(bridged_three_pin123.status, "PASS", bridged_three_pin123.issues)
            self.assertNotIn(
                POWER_INPUT_SOURCE_PATH_RULE_ID,
                {item.rule_id for item in bridged_three_pin123.findings},
            )

            unbridged_terminal = await compare(
                jumper_symbol="SolderJumper_3_Bridged12",
                jumper_pin_numbers=("1", "2", "3"),
                jumper_pin_functions=("A", "C", "B"),
                jumper_source_pin="1",
                jumper_load_pin="3",
            )
            self.assertEqual(unbridged_terminal.status, "REVIEW", unbridged_terminal.issues)
            unbridged_finding = next(
                item
                for item in unbridged_terminal.findings
                if item.rule_id == POWER_INPUT_SOURCE_PATH_RULE_ID
            )
            self.assertEqual(unbridged_finding.subject, "VLOAD: power-input source-path review")


def test_power_input_source_path_heuristic_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityPowerInputCases,
        "_case_test_power_input_source_path_heuristic_cli_mcp_parity",
    )
