"""Design-lint CLI/MCP parity cases: design lint mcp parity components."""

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
    parse_model_text,
    read_model,
    write_model,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentRoleBinding,
    ComponentRoleMap,
    ComponentRolePin,
    DesignLintPolicy,
    DesignLintReport,
    ProjectTestContract,
    ValidationSummary,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)


class _DesignLintMcpParityComponentsCases(McpParityHarness):
    async def _case_test_output_led_lint_cli_mcp_parity(self) -> None:
        """Native pin-type metadata drives the same LED review through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(output_type: str, *, custom_led: bool = False) -> None:
            led_component = (
                '<comp ref="D1"><value>LED</value>'
                "<footprint>Training:LED_0603</footprint>"
                '<fields><field name="PART_ID">training-led</field></fields>'
                '<libsource lib="Training" part="LED_5mm"/></comp>'
                if custom_led
                else '<comp ref="D1"><value>LED</value><libsource lib="Device" part="LED"/></comp>'
            )
            led_libpart = (
                '<libpart lib="Training" part="LED_5mm"><pins>'
                '<pin num="1" name="A" type="passive"/>'
                '<pin num="2" name="K" type="passive"/>'
                "</pins></libpart>"
                if custom_led
                else '<libpart lib="Device" part="LED"><pins>'
                '<pin num="1" name="A" type="passive"/>'
                '<pin num="2" name="K" type="passive"/>'
                "</pins></libpart>"
            )
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>Synthetic output</value>'
                '<libsource lib="Synthetic" part="Output"/></comp>'
                f"{led_component}"
                "</components><libparts>"
                '<libpart lib="Synthetic" part="Output"><pins>'
                f'<pin num="1" name="GPIO" type="{output_type}"/>'
                "</pins></libpart>"
                f"{led_libpart}</libparts><nets>"
                '<net name="GPIO_LED"><node ref="U1" pin="1"/>'
                '<node ref="D1" pin="1"/></net>'
                '<net name="GND"><node ref="D1" pin="2"/></net>'
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

        write_netlist("output")
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
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            fault = await compare()
            finding = next(
                item
                for item in fault.findings
                if item.rule_id == "component.led_directly_driven_from_output"
            )
            self.assertEqual(finding.evidence["output_pins"], ("U1.1",))
            self.assertEqual(finding.evidence["output_pin_types"], ("U1.1=output",))

            write_netlist("input")
            control = await compare()
            self.assertNotIn(
                "component.led_directly_driven_from_output",
                {item.rule_id for item in control.findings},
            )

            write_netlist("output", custom_led=True)
            unclassified = await compare()
            self.assertNotIn(
                "component.led_directly_driven_from_output",
                {item.rule_id for item in unclassified.findings},
            )

            contract_path = self.island / "tests/contract.json"
            test_contract = read_model(contract_path, ProjectTestContract)
            role_map = ComponentRoleMap(
                entries=(
                    ComponentRoleBinding(
                        part_id="training-led",
                        symbol="Training:LED_5mm",
                        footprint="Training:LED_0603",
                        role="led",
                        pins=(
                            ComponentRolePin(number="1", function="A", electrical_type="passive"),
                            ComponentRolePin(number="2", function="K", electrical_type="passive"),
                        ),
                        basis="Synthetic parity fixture reviewed this exact two-pin symbol identity",
                    ),
                )
            )
            project_policy = (test_contract.design_lint or DesignLintPolicy()).model_copy(
                update={"component_role_map": role_map}
            )
            write_model(
                contract_path,
                test_contract.model_copy(update={"design_lint": project_policy}),
            )
            configured_fault = await compare()
            self.assertNotEqual(unclassified.policy_sha256, configured_fault.policy_sha256)
            custom_finding = next(
                item
                for item in configured_fault.findings
                if item.rule_id == "component.led_directly_driven_from_output"
            )
            self.assertEqual(custom_finding.evidence["role_part_id"], ("training-led",))
            self.assertEqual(custom_finding.evidence["role_basis"], (role_map.entries[0].basis,))

            write_netlist("input", custom_led=True)
            configured_control = await compare()
            self.assertNotIn(
                "component.led_directly_driven_from_output",
                {item.rule_id for item in configured_control.findings},
            )

    async def _case_test_unconnected_generic_component_power_input_cli_mcp_parity(self) -> None:
        """Generic native power-input pins use the same review on both surfaces."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(connected: bool) -> None:
            supply = (
                '<net name="POWER_INPUT_TEST"><node ref="U1" pin="1"/></net>' if connected else ""
            )
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>Synthetic component</value>'
                "<footprint>Synthetic:Component</footprint>"
                '<libsource lib="Synthetic" part="GenericPowerInputComponent"/>'
                "</comp></components><libparts>"
                '<libpart lib="Synthetic" part="GenericPowerInputComponent"><pins>'
                '<pin num="1" name="1" type="power_in"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="SIGNAL"><node ref="U1" pin="2"/></net>'
                f"{supply}</nets></export>",
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

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            write_netlist(connected=False)
            fault = await compare()
            self.assertEqual(fault.status, "REVIEW", fault.issues)
            self.assertEqual(
                {item.rule_id for item in fault.findings},
                {"component.unconnected_power_input"},
            )
            self.assertEqual(
                fault.findings[0].subject,
                "U1.1: generic native power-input pin is unassigned",
            )

            write_netlist(connected=True)
            control = await compare()
            self.assertEqual(control.status, "PASS")
            self.assertNotIn(
                "component.unconnected_power_input",
                {item.rule_id for item in control.findings},
            )

    async def _case_test_custom_capacitor_role_lint_cli_mcp_parity(self) -> None:
        """An exact custom capacitor role clears only the shared LINT-046 hint."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(reference_net: str) -> None:
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>Synthetic IC</value><footprint>Synthetic:IC</footprint>'
                '<libsource lib="Synthetic" part="PowerInput"/></comp>'
                '<comp ref="U2"><value>Synthetic source</value>'
                "<footprint>Synthetic:PowerSource</footprint>"
                '<libsource lib="Synthetic" part="PowerSource"/></comp>'
                '<comp ref="C1"><value>100nF</value>'
                "<footprint>Synthetic:CAP123_0603</footprint>"
                '<fields><field name="PART_ID">synthetic-decoupling-capacitor</field></fields>'
                '<libsource lib="Vendor" part="CAP123"/></comp>'
                "</components><libparts>"
                '<libpart lib="Synthetic" part="PowerInput"><pins>'
                '<pin num="1" name="VDD" type="power_in"/>'
                '<pin num="2" name="GND" type="power_in"/>'
                "</pins></libpart>"
                '<libpart lib="Synthetic" part="PowerSource"><pins>'
                '<pin num="1" name="VOUT" type="power_out"/>'
                "</pins></libpart>"
                '<libpart lib="Vendor" part="CAP123"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="+3V3"><node ref="U1" pin="1"/>'
                '<node ref="U2" pin="1"/><node ref="C1" pin="1"/></net>'
                '<net name="GND"><node ref="U1" pin="2"/>'
                + ('<node ref="C1" pin="2"/>' if reference_net == "GND" else "")
                + "</net>"
                + (
                    '<net name="CAP_REF"><node ref="C1" pin="2"/></net>'
                    if reference_net == "CAP_REF"
                    else ""
                )
                + "</nets></export>",
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

        write_netlist("GND")
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
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            unclassified = await compare()
            self.assertEqual(unclassified.status, "REVIEW")
            self.assertIn(
                "power.ic_rail_without_fitted_capacitor",
                {item.rule_id for item in unclassified.findings},
            )

            contract_path = self.island / "tests/contract.json"
            test_contract = read_model(contract_path, ProjectTestContract)
            role_map = ComponentRoleMap(
                entries=(
                    ComponentRoleBinding(
                        part_id="synthetic-decoupling-capacitor",
                        symbol="Vendor:CAP123",
                        footprint="Synthetic:CAP123_0603",
                        role="capacitor",
                        pins=(
                            ComponentRolePin(number="1", function="1", electrical_type="passive"),
                            ComponentRolePin(number="2", function="2", electrical_type="passive"),
                        ),
                        basis="Synthetic parity fixture reviews the exact opaque capacitor identity",
                    ),
                )
            )
            project_policy = (test_contract.design_lint or DesignLintPolicy()).model_copy(
                update={"component_role_map": role_map}
            )
            write_model(
                contract_path,
                test_contract.model_copy(update={"design_lint": project_policy}),
            )
            mapped_control = await compare()
            self.assertEqual(mapped_control.status, "PASS", mapped_control.issues)
            self.assertNotIn(
                "power.ic_rail_without_fitted_capacitor",
                {item.rule_id for item in mapped_control.findings},
            )

            write_netlist("CAP_REF")
            mapped_fault = await compare()
            self.assertEqual(mapped_fault.status, "REVIEW")
            self.assertIn(
                "power.ic_rail_without_fitted_capacitor",
                {item.rule_id for item in mapped_fault.findings},
            )


def test_output_led_lint_cli_mcp_parity() -> None:
    run_mcp_parity(_DesignLintMcpParityComponentsCases, "_case_test_output_led_lint_cli_mcp_parity")


def test_unconnected_generic_component_power_input_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityComponentsCases,
        "_case_test_unconnected_generic_component_power_input_cli_mcp_parity",
    )


def test_custom_capacitor_role_lint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityComponentsCases, "_case_test_custom_capacitor_role_lint_cli_mcp_parity"
    )
