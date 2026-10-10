"""Design-lint CLI/MCP parity cases: design lint mcp parity power paths."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
]

import xml.etree.ElementTree as ET

from mcp import Client

from kicad_tooling.hwrepo.contracts import (
    read_model,
    write_model,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentIdentity,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    ProjectManifest,
    ProjectTestContract,
    ValidationSummary,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)
from tests.power_sequence_support import RULE_ID as POWER_SEQUENCE_RULE_ID
from tests.power_sequence_support import power_sequence_map as synthetic_power_sequence_map
from tests.power_sequence_support import (
    power_sequence_output_cycle_map as synthetic_power_sequence_output_cycle_map,
)
from tests.power_sequence_support import (
    power_sequence_output_cycle_netlist as synthetic_power_sequence_output_cycle_netlist,
)
from tests.test_power_paths import RULE_ID as POWER_PATH_RULE_ID
from tests.test_power_paths import power_path_map as synthetic_power_path_map


class _DesignLintMcpParityPowerPathsCases(McpParityHarness):
    async def _case_test_power_path_map_parity(self) -> None:
        """Compare a required ferrite path fault through the CLI and MCP adapters."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(*, open_ferrite: bool) -> None:
            if open_ferrite:
                downstream_nets = (
                    '<net name="VLOAD"><node ref="U1" pin="3"/></net>'
                    '<net name="FLOATING"><node ref="FB1" pin="2"/></net>'
                )
            else:
                downstream_nets = (
                    '<net name="VLOAD"><node ref="FB1" pin="2"/><node ref="U1" pin="3"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="J1"><value>Synthetic source</value>'
                "<footprint>Synthetic:Conn2</footprint>"
                '<libsource lib="Synthetic" part="PowerInput"/></comp>'
                '<comp ref="FB1"><value>Ferrite bead</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="FerriteBead"/></comp>'
                '<comp ref="U1"><value>Synthetic controller</value>'
                "<footprint>Synthetic:QFN</footprint>"
                '<libsource lib="Synthetic" part="Controller"/></comp>'
                "</components><libparts>"
                '<libpart lib="Synthetic" part="PowerInput"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart>"
                '<libpart lib="Device" part="FerriteBead"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart>"
                '<libpart lib="Synthetic" part="Controller"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                '<pin num="3" name="VDD" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="VIN"><node ref="J1" pin="1"/>'
                '<node ref="FB1" pin="1"/></net>'
                f"{downstream_nets}"
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

        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "component_identity": ComponentIdentity(required=False, part_ids=()),
                    "interfaces": (),
                    "connector_reviews": (
                        ConnectorInterfaceReview(
                            reference="J1",
                            disposition="not_applicable",
                            basis="Synthetic parity case checks only the mapped power topology",
                        ),
                    ),
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic parity fixture reviewed its power input interface"
                    ),
                }
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={"design_lint": DesignLintPolicy(power_path_map=synthetic_power_path_map())}
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(*, fault: bool) -> DesignLintReport:
                write_netlist(open_ferrite=fault)
                exit_code = 1 if fault else 0
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

            control = await compare(fault=False)
            self.assertEqual(control.status, "PASS", control.issues)
            self.assertNotIn(POWER_PATH_RULE_ID, {item.rule_id for item in control.findings})

            fault = await compare(fault=True)
            self.assertEqual(fault.status, "REVIEW", fault.issues)
            finding = next(item for item in fault.findings if item.rule_id == POWER_PATH_RULE_ID)
            self.assertEqual(finding.subject, "input-to-controller: required power path differs")

    async def _case_test_power_sequence_map_parity(self) -> None:
        """Compare a mapped sequence fault through native XML, CLI, and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(*, open_enable: bool) -> None:
            if open_enable:
                control_nets = (
                    '<net name="GOOD_A"><node ref="U1" pin="3"/></net>'
                    '<net name="FLOATING"><node ref="U2" pin="1"/></net>'
                )
            else:
                control_nets = (
                    '<net name="GOOD_A"><node ref="U1" pin="3"/><node ref="U2" pin="1"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>Synthetic regulator A</value>'
                "<footprint>Synthetic:SOT23-5</footprint><fields>"
                '<field name="PART_ID">SYNTH-REG-A</field></fields>'
                '<libsource lib="Synthetic" part="Regulator"/></comp>'
                '<comp ref="U2"><value>Synthetic regulator B</value>'
                "<footprint>Synthetic:SOT23-5</footprint><fields>"
                '<field name="PART_ID">SYNTH-REG-B</field></fields>'
                '<libsource lib="Synthetic" part="Regulator"/></comp>'
                "</components><libparts>"
                '<libpart lib="Synthetic" part="Regulator"><pins>'
                '<pin num="1" name="P1" type="passive"/>'
                '<pin num="2" name="P2" type="passive"/>'
                '<pin num="3" name="P3" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="CONTROL_ON"><node ref="U1" pin="1"/></net>'
                '<net name="RAIL_A"><node ref="U1" pin="2"/></net>'
                f"{control_nets}"
                '<net name="RAIL_B"><node ref="U2" pin="2"/></net>'
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

        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        power_sequence_map=synthetic_power_sequence_map()
                    )
                }
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:
            for open_enable in (False, True):
                with self.subTest(open_enable=open_enable):
                    write_netlist(open_enable=open_enable)
                    cli = await self.cli(
                        "kicad_tooling.design_lint",
                        DesignLintReport,
                        "--project",
                        "controller",
                        "--native-summary",
                        str(native),
                        expected_exit=int(open_enable),
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
                    findings = [
                        item for item in mcp.findings if item.rule_id == POWER_SEQUENCE_RULE_ID
                    ]
                    self.assertEqual(len(findings), int(open_enable))
                    self.assertEqual(mcp.status, "REVIEW" if open_enable else "PASS")
                    if open_enable:
                        self.assertEqual(
                            findings[0].subject,
                            "rail-b: required power-sequence stage differs",
                        )

    async def _case_test_mapped_output_to_enable_cycle_parity(self) -> None:
        """Compare an inferred mapped-endpoint cycle through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        contract_path = self.island / "tests/contract.json"

        def write_case(*, cycle: bool) -> None:
            observed = synthetic_power_sequence_output_cycle_netlist(cycle=cycle)
            root = ET.Element("export")
            component_container = ET.SubElement(root, "components")
            for reference, component in observed.components.items():
                comp = ET.SubElement(component_container, "comp", ref=reference)
                ET.SubElement(comp, "value").text = component.value
                ET.SubElement(comp, "footprint").text = component.footprint
                fields = ET.SubElement(comp, "fields")
                ET.SubElement(fields, "field", name="PART_ID").text = component.part_id
                ET.SubElement(comp, "libsource", lib="Synthetic", part="Regulator")
            libparts = ET.SubElement(root, "libparts")
            libpart = ET.SubElement(libparts, "libpart", lib="Synthetic", part="Regulator")
            pins = ET.SubElement(libpart, "pins")
            for number, name in (("1", "EN"), ("2", "OUT"), ("3", "PG")):
                ET.SubElement(pins, "pin", num=number, name=name, type="passive")
            nets = ET.SubElement(root, "nets")
            for net_name, net_pins in sorted(observed.nets.items()):
                if not net_pins:
                    continue
                net = ET.SubElement(nets, "net", name=net_name)
                for pin in net_pins:
                    reference, number = pin.split(".", maxsplit=1)
                    ET.SubElement(net, "node", ref=reference, pin=number)
            netlist.write_bytes(ET.tostring(root, encoding="utf-8"))
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
            contract = read_model(contract_path, ProjectTestContract)
            write_model(
                contract_path,
                contract.model_copy(
                    update={
                        "design_lint": DesignLintPolicy(
                            power_sequence_map=synthetic_power_sequence_output_cycle_map(
                                cycle=cycle
                            )
                        )
                    }
                ),
            )

        async with Client(create_server(self.root), mode="legacy") as client:
            for cycle in (False, True):
                with self.subTest(cycle=cycle):
                    write_case(cycle=cycle)
                    cli = await self.cli(
                        "kicad_tooling.design_lint",
                        DesignLintReport,
                        "--project",
                        "controller",
                        "--native-summary",
                        str(native),
                        expected_exit=int(cycle),
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
                    findings = [
                        item for item in mcp.findings if item.rule_id == POWER_SEQUENCE_RULE_ID
                    ]
                    self.assertEqual(len(findings), int(cycle))
                    self.assertEqual(mcp.status, "REVIEW" if cycle else "PASS")
                    if cycle:
                        self.assertEqual(
                            findings[0].evidence["observed_output_to_enable_cycle_stages"],
                            ("rail-a, rail-b",),
                        )


def test_power_path_map_parity() -> None:
    run_mcp_parity(_DesignLintMcpParityPowerPathsCases, "_case_test_power_path_map_parity")


def test_power_sequence_map_parity() -> None:
    run_mcp_parity(_DesignLintMcpParityPowerPathsCases, "_case_test_power_sequence_map_parity")


def test_mapped_output_to_enable_cycle_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityPowerPathsCases, "_case_test_mapped_output_to_enable_cycle_parity"
    )
