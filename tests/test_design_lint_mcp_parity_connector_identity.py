"""Design-lint CLI/MCP parity cases: design lint mcp parity connector identity."""

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
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintReport,
    InterfacePin,
    InterfaceRecord,
    InterfacesCatalog,
    ProjectManifest,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)


class _DesignLintMcpParityConnectorIdentityCases(McpParityHarness):
    async def _case_test_standard_and_reviewed_custom_connector_identity_cli_mcp_parity(
        self,
    ) -> None:
        """Share standard and explicitly reviewed custom connector identity across surfaces."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(*, common_return: bool, supply_connected: bool) -> None:
            if common_return:
                return_net = (
                    '<net name="GND"><node ref="J1" pin="1"/>'
                    '<node ref="U7" pin="1"/><node ref="A1" pin="1"/>'
                    '<node ref="A2" pin="1"/><node ref="A3" pin="1"/></net>'
                )
            else:
                return_net = (
                    '<net name="GND_A"><node ref="J1" pin="1"/></net>'
                    '<net name="GND_B"><node ref="U7" pin="1"/></net>'
                    '<net name="CUSTOM_GND_A"><node ref="A1" pin="1"/>'
                    '<node ref="A2" pin="1"/></net>'
                    '<net name="CUSTOM_GND_B"><node ref="A3" pin="1"/></net>'
                )
            second_supply = '<node ref="U7" pin="2"/>' if supply_connected else ""
            data_pins = '<node ref="J1" pin="3"/><node ref="U7" pin="3"/>'
            custom_supply = (
                '<net name="CUSTOM_SUPPLY"><node ref="A1" pin="2"/>'
                '<node ref="A2" pin="2"/><node ref="A3" pin="2"/></net>'
                if supply_connected
                else '<net name="CUSTOM_SUPPLY_A"><node ref="A1" pin="2"/>'
                '<node ref="A2" pin="2"/></net>'
                '<net name="CUSTOM_SUPPLY_B"><node ref="A3" pin="2"/></net>'
            )
            netlist.write_text(
                "<export><components>"
                '<comp ref="J1"><value>Port A</value>'
                '<libsource lib="Connector_Generic" part="Conn_01x03"/></comp>'
                '<comp ref="U7"><value>Port B</value>'
                '<libsource lib="Connector_Generic" part="Conn_01x03"/></comp>'
                '<comp ref="A1"><value>Custom Port A</value>'
                '<libsource lib="Synthetic" part="CustomPort"/></comp>'
                '<comp ref="A2"><value>Custom Port B</value>'
                '<libsource lib="Synthetic" part="CustomPort"/></comp>'
                '<comp ref="A3"><value>Custom Port C</value>'
                '<libsource lib="Synthetic" part="CustomPort"/></comp>'
                "</components><libparts>"
                '<libpart lib="Connector_Generic" part="Conn_01x03"><pins>'
                '<pin num="1" name="GND" type="passive"/>'
                '<pin num="2" name="VBUS" type="passive"/>'
                '<pin num="3" name="DATA" type="passive"/>'
                "</pins></libpart>"
                '<libpart lib="Synthetic" part="CustomPort"><pins>'
                '<pin num="1" name="Pin_1" type="passive"/>'
                '<pin num="2" name="Pin_2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                f"{return_net}"
                f'<net name="+5V"><node ref="J1" pin="2"/>{second_supply}</net>'
                f'<net name="DATA">{data_pins}</net>'
                f"{custom_supply}"
                "</nets></export>",
                encoding="utf-8",
            )
            self.rehash_native_netlist(native)

        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        custom_reviews = tuple(
            ConnectorInterfaceReview(
                reference=reference,
                disposition="interface",
                interface_id="synthetic-port",
                basis="Synthetic reviewed custom connector pinout",
                pin_map={"1": "1", "2": "2"},
            )
            for reference in ("A1", "A2", "A3")
        )

        def set_custom_connector_review(
            enabled: bool,
            *,
            references: tuple[str, ...] = ("A1", "A2", "A3"),
        ) -> None:
            selected_reviews = (
                tuple(item for item in custom_reviews if item.reference in references)
                if enabled
                else ()
            )
            write_model(
                manifest_path,
                manifest.model_copy(
                    update={
                        "interfaces": ("synthetic-port",) if selected_reviews else (),
                        "connector_reviews": selected_reviews,
                        "connector_inventory_review": ConnectorInventoryReview(
                            basis="Synthetic review covered the connector inventory"
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
                        id="synthetic-port",
                        revision="synthetic-1",
                        pins=(
                            InterfacePin(
                                number="1",
                                signal="GND",
                                role="return",
                                direction="bidirectional",
                                voltage_domain="synthetic-reference",
                                mating="synthetic peer",
                                orientation="straight",
                                mechanical_clearance="synthetic",
                            ),
                            InterfacePin(
                                number="2",
                                signal="POWER",
                                role="supply",
                                direction="bidirectional",
                                voltage_domain="external-5v",
                                mating="synthetic peer",
                                orientation="straight",
                                mechanical_clearance="synthetic",
                            ),
                        ),
                    ),
                ),
            ),
        )
        set_custom_connector_review(True)
        write_netlist(common_return=False, supply_connected=False)
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
            assert fault.connector_peer_pin_coverage is not None
            self.assertEqual(
                fault.connector_peer_pin_coverage.netlist_sha256,
                fault.netlist_sha256,
            )
            self.assertEqual(
                fault.connector_peer_pin_coverage.repeated_function_finding_count,
                sum(item.rule_id == "connector.repeated_pin_function" for item in fault.findings),
            )
            repeated_rule_ids = {
                item.rule_id
                for item in fault.findings
                if item.rule_id
                in {
                    "connector.peer_pin_assignment_outlier",
                    "connector.peer_pin_assignment_divergence",
                }
            }
            self.assertFalse(
                repeated_rule_ids,
                "fully mapped generic connector peers should use the more specific role finding",
            )
            repeated_groups = tuple(
                item.evidence
                for item in fault.findings
                if item.rule_id == "connector.repeated_pin_function"
            )
            self.assertTrue(any("U7.1" in evidence for evidence in repeated_groups))
            self.assertTrue(any("U7.2" in evidence for evidence in repeated_groups))
            self.assertTrue(
                any("A1.1" in evidence and "A2.1" in evidence for evidence in repeated_groups)
            )
            self.assertTrue(any("A3.1" in evidence for evidence in repeated_groups))
            custom_return = next(
                evidence
                for evidence in repeated_groups
                if "A1.1" in evidence and "A2.1" in evidence
            )
            self.assertEqual(custom_return["A1.1"], ("CUSTOM_GND_A",))
            self.assertEqual(custom_return["A2.1"], ("CUSTOM_GND_A",))
            self.assertEqual(custom_return["A3.1"], ("CUSTOM_GND_B",))
            custom_supply = next(
                item
                for item in fault.findings
                if "same source-reviewed voltage domain" in item.message
            )
            self.assertEqual(custom_supply.evidence["A1.2"], ("CUSTOM_SUPPLY_A",))
            self.assertEqual(custom_supply.evidence["A2.2"], ("CUSTOM_SUPPLY_A",))
            self.assertEqual(custom_supply.evidence["A3.2"], ("CUSTOM_SUPPLY_B",))
            self.assertEqual(
                custom_supply.evidence["role_classification_sources"],
                (
                    (
                        "A1.2: project interface catalog role=supply; "
                        "voltage_domain=external-5v; native symbol function=Pin_2"
                    ),
                    (
                        "A2.2: project interface catalog role=supply; "
                        "voltage_domain=external-5v; native symbol function=Pin_2"
                    ),
                    (
                        "A3.2: project interface catalog role=supply; "
                        "voltage_domain=external-5v; native symbol function=Pin_2"
                    ),
                ),
            )
            self.assertEqual(custom_supply.evidence["reviewed_voltage_domain"], ("external-5v",))
            assert fault.connector_coverage is not None
            self.assertEqual(
                {
                    item.reference: item.status
                    for item in fault.connector_coverage.entries
                    if item.reference in {"A1", "A2", "A3"}
                },
                {"A1": "COVERED", "A2": "COVERED", "A3": "COVERED"},
            )

            set_custom_connector_review(True, references=("A1", "A3"))
            partial_map = await compare()
            assert partial_map.connector_coverage is not None
            self.assertEqual(
                next(
                    item.status
                    for item in partial_map.connector_coverage.entries
                    if item.reference == "A2"
                ),
                "UNDECLARED",
            )
            partial_role_findings = tuple(
                item
                for item in partial_map.findings
                if item.rule_id == "connector.repeated_pin_function"
                and "A1.1" in item.evidence
                and "A3.1" in item.evidence
            )
            self.assertTrue(partial_role_findings)
            self.assertFalse(
                {
                    item.rule_id
                    for item in partial_map.findings
                    if item.rule_id
                    in {
                        "connector.peer_pin_assignment_outlier",
                        "connector.peer_pin_assignment_divergence",
                    }
                    and item.evidence.get("symbol") == ("Synthetic:CustomPort",)
                },
                "the mapped role finding fully covers the two compared peers",
            )

            set_custom_connector_review(False)
            unreviewed_custom = await compare()
            assert unreviewed_custom.connector_coverage is not None
            self.assertFalse(
                {item.reference for item in unreviewed_custom.connector_coverage.entries}
                & {"A1", "A2", "A3"}
            )
            self.assertFalse(
                any(
                    pin.startswith(("A1.", "A2.", "A3."))
                    for item in unreviewed_custom.findings
                    if item.rule_id == "connector.repeated_pin_function"
                    for pin in item.evidence
                )
            )

            set_custom_connector_review(True)
            write_netlist(common_return=True, supply_connected=True)
            control = await compare()
            self.assertNotIn(
                "connector.repeated_pin_function",
                {item.rule_id for item in control.findings},
            )

            netlist.write_text(
                "<export><components>"
                + "".join(
                    f'<comp ref="J{index}"><value>Generic peer port</value>'
                    '<libsource lib="Connector_Generic" part="Conn_01x02"/></comp>'
                    for index in range(1, 4)
                )
                + "</components><libparts>"
                '<libpart lib="Connector_Generic" part="Conn_01x02"><pins>'
                '<pin num="1" name="Pin_1" type="passive"/>'
                '<pin num="2" name="Pin_2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                + "".join(
                    f'<net name="PORT_{pin}_{peer}"><node ref="J{peer}" pin="{pin}"/></net>'
                    for pin in (1, 2)
                    for peer in range(1, 4)
                )
                + "</nets></export>",
                encoding="utf-8",
            )
            self.rehash_native_netlist(native)
            placeholders = await compare()
            placeholder_divergences = [
                item
                for item in placeholders.findings
                if item.rule_id == "connector.peer_pin_assignment_divergence"
            ]
            self.assertEqual(len(placeholder_divergences), 2)
            self.assertFalse(
                any(
                    item.rule_id == "connector.repeated_pin_function"
                    for item in placeholders.findings
                )
            )
            self.assertTrue(
                all(
                    item.evidence["missing_pin_function_pins"] == ("J1.1", "J2.1", "J3.1")
                    if item.subject.endswith("pin 1")
                    else item.evidence["missing_pin_function_pins"] == ("J1.2", "J2.2", "J3.2")
                    for item in placeholder_divergences
                )
            )

            peer_interface = InterfaceRecord(
                id="generic-peer-port",
                revision="synthetic-1",
                pins=tuple(
                    InterfacePin(
                        number=number,
                        signal=f"SIGNAL_{number}",
                        role="signal",
                        direction="bidirectional",
                        voltage_domain="logic-3v3",
                        mating=f"SIGNAL_{number}",
                        orientation="straight",
                        mechanical_clearance="synthetic",
                    )
                    for number in ("1", "2")
                ),
            )
            write_model(
                self.root / "catalog/interfaces.json",
                InterfacesCatalog(schema_version="1", interfaces=(peer_interface,)),
            )

            def set_generic_peer_groups(groups: tuple[str, ...]) -> None:
                references = ("J1", "J2", "J3")
                selected = tuple(
                    ConnectorInterfaceReview(
                        reference=reference,
                        disposition="interface",
                        interface_id="generic-peer-port",
                        basis=f"Reviewed {reference} as an external signal interface",
                        pin_map={"1": "1", "2": "2"},
                        peer_assignment_group=groups[index],
                        peer_assignment_basis=(
                            f"Reviewed {reference} within peer-assignment group {groups[index]}"
                        ),
                    )
                    for index, reference in enumerate(references)
                )
                write_model(
                    manifest_path,
                    manifest.model_copy(
                        update={
                            "interfaces": ("generic-peer-port",),
                            "connector_reviews": selected,
                            "connector_inventory_review": ConnectorInventoryReview(
                                basis="Synthetic review covered the generic connector inventory"
                            ),
                        }
                    ),
                )

            set_generic_peer_groups(("uart-1", "uart-2", "uart-3"))
            separate_groups = await compare()
            self.assertFalse(
                {
                    item.rule_id
                    for item in separate_groups.findings
                    if item.rule_id
                    in {
                        "connector.peer_pin_assignment_outlier",
                        "connector.peer_pin_assignment_divergence",
                    }
                }
            )
            assert separate_groups.connector_coverage is not None
            self.assertEqual(
                {
                    entry.reference: entry.peer_assignment_group
                    for entry in separate_groups.connector_coverage.entries
                },
                {"J1": "uart-1", "J2": "uart-2", "J3": "uart-3"},
            )

            set_generic_peer_groups(("uart-ports", "uart-ports", "uart-ports"))
            same_group = await compare()
            same_group_findings = tuple(
                item
                for item in same_group.findings
                if item.rule_id == "connector.peer_pin_assignment_divergence"
            )
            self.assertEqual(len(same_group_findings), 2)
            self.assertTrue(
                all(
                    item.evidence["peer_assignment_group"] == ("uart-ports",)
                    for item in same_group_findings
                )
            )

            set_generic_peer_groups(("uart-1", "uart-2", "uart-3"))
            set_generic_peer_reviews = read_model(manifest_path, ProjectManifest)
            write_model(
                manifest_path,
                set_generic_peer_reviews.model_copy(
                    update={"connector_reviews": set_generic_peer_reviews.connector_reviews[:2]}
                ),
            )
            partial_group = await compare()
            self.assertTrue(
                any(
                    item.rule_id == "connector.peer_pin_assignment_divergence"
                    for item in partial_group.findings
                ),
                "an unreviewed connector keeps the conservative peer comparison active",
            )


def test_standard_and_reviewed_custom_connector_identity_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityConnectorIdentityCases,
        "_case_test_standard_and_reviewed_custom_connector_identity_cli_mcp_parity",
    )
