"""Design-lint CLI/MCP parity cases: design lint mcp parity connector returns."""

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
    ComponentIdentity,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    ConnectorReturnDistributionMap,
    ConnectorReturnDistributionRequirement,
    DesignLintPolicy,
    DesignLintReport,
    InterfacePin,
    InterfaceRecord,
    InterfacesCatalog,
    ProjectManifest,
    ProjectTestContract,
    ValidationSummary,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)


class _DesignLintMcpParityConnectorReturnsCases(McpParityHarness):
    async def _case_test_connector_capacitor_only_dc_reference_lint_cli_mcp_parity(self) -> None:
        """Compare a connector/capacitor-only net hint and local-driver control."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(with_driver: bool) -> None:
            driver_component = (
                '<comp ref="U1"><value>Synthetic output</value>'
                '<libsource lib="Synthetic" part="SignalDriver"/></comp>'
                if with_driver
                else ""
            )
            driver_libpart = (
                '<libpart lib="Synthetic" part="SignalDriver"><pins>'
                '<pin num="1" name="OUT" type="output"/></pins></libpart>'
                if with_driver
                else ""
            )
            driver_node = '<node ref="U1" pin="1"/>' if with_driver else ""
            netlist.write_text(
                "<export><components>"
                '<comp ref="J1"><value>Synthetic input connector</value>'
                '<libsource lib="Connector_Generic" part="Conn_01x02"/></comp>'
                '<comp ref="C1"><value>100n</value>'
                '<libsource lib="Device" part="C"/></comp>'
                f"{driver_component}</components><libparts>"
                '<libpart lib="Connector_Generic" part="Conn_01x02"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/></pins></libpart>'
                '<libpart lib="Device" part="C"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/></pins></libpart>'
                f"{driver_libpart}</libparts><nets>"
                '<net name="ANALOG_IN"><node ref="J1" pin="1"/>'
                f'<node ref="C1" pin="1"/>{driver_node}</net>'
                '<net name="GND"><node ref="J1" pin="2"/>'
                '<node ref="C1" pin="2"/></net>'
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

        write_netlist(with_driver=False)
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
            self.assertEqual(fault.status, "REVIEW")
            finding = next(
                item
                for item in fault.findings
                if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
            )
            self.assertEqual(finding.evidence["connector_pins"], ("J1.1",))
            self.assertEqual(finding.evidence["capacitor_pins"], ("C1.1",))

            write_netlist(with_driver=True)
            control = await compare()
            self.assertNotIn(
                "net.connector_capacitor_only_no_dc_anchor",
                {item.rule_id for item in control.findings},
            )

    async def _case_test_connector_return_distribution_map_parity(self) -> None:
        """Compare role-based return-distribution review through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        roles = ("signal",) * 6 + ("return", "supply", "shield")
        pin_names = tuple(f"SIG{number}" for number in range(1, 7)) + (
            "GND",
            "VCC",
            "SHIELD",
        )
        component_pins = "".join(
            f'<pin num="{number}" name="{name}" type="passive"/>'
            for number, name in enumerate(pin_names, start=1)
        )
        net_nodes = "".join(
            f'<net name="NET_{number:02d}"><node ref="J1" pin="{number}"/></net>'
            for number in range(1, len(roles) + 1)
        )
        netlist.write_text(
            "<export><components>"
            '<comp ref="J1"><value>Synthetic external interface</value>'
            "<footprint>Synthetic:Port</footprint>"
            '<libsource lib="Synthetic" part="ExternalPort"/></comp>'
            "</components><libparts>"
            '<libpart lib="Synthetic" part="ExternalPort"><pins>'
            + component_pins
            + "</pins></libpart></libparts><nets>"
            + net_nodes
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

        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "component_identity": ComponentIdentity(required=False, part_ids=()),
                    "interfaces": ("synthetic-link",),
                    "connector_reviews": (
                        ConnectorInterfaceReview(
                            reference="J1",
                            disposition="interface",
                            interface_id="synthetic-link",
                            basis="Synthetic reviewed connector interface",
                            pin_map={str(number): str(number) for number in range(1, 10)},
                        ),
                    ),
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic review covered all connector candidates in the schematic"
                    ),
                }
            ),
        )
        write_model(
            self.root / "catalog/interfaces.json",
            InterfacesCatalog(
                schema_version="1",
                interfaces=(
                    InterfaceRecord(
                        id="synthetic-link",
                        revision="synthetic-1",
                        pins=tuple(
                            InterfacePin(
                                number=str(number),
                                signal=f"contact-{number}",
                                role=role,
                                direction="bidirectional",
                                voltage_domain="synthetic-domain",
                                mating="synthetic peer",
                                orientation="straight",
                                mechanical_clearance="synthetic",
                            )
                            for number, role in enumerate(roles, start=1)
                        ),
                    ),
                ),
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        policy = DesignLintPolicy(
            connector_return_distribution_map=ConnectorReturnDistributionMap(
                requirements=(
                    ConnectorReturnDistributionRequirement(
                        id="external-link",
                        interface_id="synthetic-link",
                        minimum_signal_pin_count=4,
                        maximum_signal_to_return_ratio=3.0,
                        basis="Synthetic authored signal/return contact threshold",
                    ),
                )
            )
        )
        write_model(contract_path, contract.model_copy(update={"design_lint": policy}))

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
        self.assertEqual(mcp.status, "REVIEW", mcp.issues)
        self.assertEqual(mcp.connector_return_distribution.status, "COMPLETE")
        self.assertEqual(mcp.connector_return_distribution.entries[0].signal_pin_count, 6)
        self.assertEqual(mcp.connector_return_distribution.entries[0].return_pin_count, 1)
        self.assertTrue(
            any(item.rule_id == "connector.return_distribution" for item in mcp.findings)
        )


def test_connector_capacitor_only_dc_reference_lint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityConnectorReturnsCases,
        "_case_test_connector_capacitor_only_dc_reference_lint_cli_mcp_parity",
    )


def test_connector_return_distribution_map_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityConnectorReturnsCases,
        "_case_test_connector_return_distribution_map_parity",
    )
