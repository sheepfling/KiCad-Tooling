"""Connector review coverage remains distinct from inferred connectivity."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from kicad_tooling.hwrepo.connector_coverage import (
    evaluate,
    source_matched_connector_peer_assignment_groups,
)
from kicad_tooling.hwrepo.connector_pins import connector_peer_pin_assignment_outliers
from kicad_tooling.hwrepo.design_lint import (
    evaluate as evaluate_design_lint,
)
from kicad_tooling.hwrepo.design_lint import (
    text_report,
)
from kicad_tooling.hwrepo.models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
    InterfacePin,
    InterfaceRecord,
    NetlistContract,
)


def inventory_review() -> ConnectorInventoryReview:
    return ConnectorInventoryReview(
        basis="Synthetic review covered the complete schematic symbol inventory"
    )


def interface_record() -> InterfaceRecord:
    return InterfaceRecord(
        id="debug-port",
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="TX",
                direction="output",
                voltage_domain="logic-3v3",
                mating="RX",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="2",
                signal="RX",
                direction="input",
                voltage_domain="logic-3v3",
                mating="TX",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )


def observed_connector(*, candidate: bool = True) -> NetlistContract:
    return NetlistContract(
        components={},
        nets={"TX": ("J1.1",)},
        component_symbols={"J1": "Synthetic:DebugConnector"} if candidate else {},
        component_pin_numbers={"J1": ("1", "2", "3")} if candidate else {},
    )


def connector_return_role_netlist(
    *,
    common_return: bool = False,
    open_return: bool = False,
    open_supply: bool = False,
) -> NetlistContract:
    return_nets = {"USB_RETURN": ("J1.3",), "SERIAL_RETURN": ("J2.3",)}
    if common_return:
        return_nets = {"COMMON_RETURN": ("J1.3",) if open_return else ("J1.3", "J2.3")}
    elif open_return:
        return_nets = {"USB_RETURN": ("J1.3",)}
    return NetlistContract(
        components={},
        nets={
            **return_nets,
            "USB_DATA_1": ("J1.1",),
            "USB_DATA_2": ("J1.2",),
            "SERIAL_TX": ("J2.1",),
            "SERIAL_RX": ("J2.2",),
            **({} if open_supply else {"SERIAL_SUPPLY": ("J2.4",)}),
        },
        component_symbols={"J1": "Connector:USB_C_Receptacle_USB2.0_16P", "J2": "Connector:DB9"},
        component_pin_numbers={"J1": ("1", "2", "3"), "J2": ("1", "2", "3", "4")},
        pin_functions={
            "J1.1": "D+",
            "J1.2": "D-",
            "J1.3": "GND",
            "J2.1": "TX",
            "J2.2": "RX",
            "J2.3": "Pin_3",
            "J2.4": "Pin_4",
        },
    )


def uart_peer_netlist(*, split_return: bool = False) -> NetlistContract:
    return_nets = (
        {"UART1_RETURN": ("J1.3",), "UART2_RETURN": ("J2.3",)}
        if split_return
        else {"GND": ("J1.3", "J2.3")}
    )
    return NetlistContract(
        components={},
        nets={
            **return_nets,
            "UART1_TX": ("J1.1",),
            "UART1_RX": ("J1.2",),
            "UART2_TX": ("J2.1",),
            "UART2_RX": ("J2.2",),
        },
        component_symbols={
            "J1": "Connector_Generic:Conn_01x03",
            "J2": "Connector_Generic:Conn_01x03",
        },
        component_pin_numbers={"J1": ("1", "2", "3"), "J2": ("1", "2", "3")},
        pin_functions={
            f"{reference}.{pin}": f"Pin_{pin}"
            for reference in ("J1", "J2")
            for pin in ("1", "2", "3")
        },
    )


def uart_header_interface(identifier: str) -> InterfaceRecord:
    return InterfaceRecord(
        id=identifier,
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="TX",
                role="signal",
                direction="output",
                voltage_domain="logic-3v3",
                mating="RX",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="2",
                signal="RX",
                role="signal",
                direction="input",
                voltage_domain="logic-3v3",
                mating="TX",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="3",
                signal="GND",
                role="return",
                direction="passive",
                voltage_domain="signal-return",
                mating="GND",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )


def uart_header_coverage(
    observed: NetlistContract,
    *,
    groups: tuple[str, str],
    reverse_inputs: bool = False,
) -> ConnectorCoverageReport:
    identifiers = ("uart-header-1", "uart-header-2")
    interfaces = {identifier: uart_header_interface(identifier) for identifier in identifiers}
    review_pairs = tuple(zip(("J1", "J2"), identifiers, groups, strict=True))
    if reverse_inputs:
        identifiers = tuple(reversed(identifiers))
        interfaces = dict(reversed(tuple(interfaces.items())))
        review_pairs = tuple(reversed(review_pairs))
    reviews = tuple(
        ConnectorInterfaceReview(
            reference=reference,
            disposition="interface",
            basis=f"Reviewed {reference} as a separate 3.3 V UART interface",
            interface_id=interface_id,
            pin_map={"1": "1", "2": "2", "3": "3"},
            peer_assignment_group=group,
            peer_assignment_basis=(
                f"Reviewed {reference} as a member of peer-assignment group {group}"
            ),
        )
        for reference, interface_id, group in review_pairs
    )
    return evaluate(
        observed,
        identifiers,
        reviews,
        interfaces=interfaces,
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="a" * 64,
        inventory_review=inventory_review(),
    )


def connector_return_role_catalog() -> dict[str, InterfaceRecord]:
    return {
        "usb-interface": InterfaceRecord(
            id="usb-interface",
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="1",
                    signal="D+",
                    role="signal",
                    direction="bidirectional",
                    voltage_domain="logic",
                    mating="D+",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
                InterfacePin(
                    number="2",
                    signal="D-",
                    role="signal",
                    direction="bidirectional",
                    voltage_domain="logic",
                    mating="D-",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
                InterfacePin(
                    number="3",
                    signal="GND",
                    role="return",
                    direction="passive",
                    voltage_domain="return",
                    mating="GND",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        ),
        "serial-interface": InterfaceRecord(
            id="serial-interface",
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="1",
                    signal="TX",
                    role="signal",
                    direction="output",
                    voltage_domain="logic",
                    mating="RX",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
                InterfacePin(
                    number="2",
                    signal="RX",
                    role="signal",
                    direction="input",
                    voltage_domain="logic",
                    mating="TX",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
                InterfacePin(
                    number="3",
                    signal="RETURN",
                    role="return",
                    direction="passive",
                    voltage_domain="return",
                    mating="RETURN",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
                InterfacePin(
                    number="4",
                    signal="V+",
                    role="supply",
                    direction="passive",
                    voltage_domain="power",
                    mating="V+",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        ),
    }


def connector_return_role_reviews() -> tuple[ConnectorInterfaceReview, ...]:
    return (
        ConnectorInterfaceReview(
            reference="J1",
            disposition="interface",
            basis="Synthetic USB interface map reviewed",
            interface_id="usb-interface",
            pin_map={"1": "1", "2": "2", "3": "3"},
        ),
        ConnectorInterfaceReview(
            reference="J2",
            disposition="interface",
            basis="Synthetic serial interface map reviewed",
            interface_id="serial-interface",
            pin_map={"1": "1", "2": "2", "3": "3", "4": "4"},
        ),
    )


def connector_supply_role_netlist(
    *, common_supply: bool = False, open_supply: bool = False
) -> NetlistContract:
    if open_supply:
        supply_nets = {"NODE_ALPHA": ("J1.2",)}
    elif common_supply:
        supply_nets = {"SHARED_SUPPLY": ("J1.2", "J2.5")}
    else:
        supply_nets = {"NODE_ALPHA": ("J1.2",), "NODE_BETA": ("J2.5",)}
    return NetlistContract(
        components={},
        nets=supply_nets,
        component_symbols={"J1": "Synthetic:UsbPort", "J2": "Synthetic:SerialPort"},
        component_pin_numbers={"J1": ("2",), "J2": ("5",)},
        pin_functions={"J1.2": "2", "J2.5": "Pin_5"},
    )


def connector_supply_role_catalog(
    *, serial_voltage_domain: str = "external-5v"
) -> dict[str, InterfaceRecord]:
    return {
        interface_id: InterfaceRecord(
            id=interface_id,
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number=pin_number,
                    signal="POWER",
                    role="supply",
                    direction="passive",
                    voltage_domain=(
                        serial_voltage_domain if interface_id == "serial-power" else "external-5v"
                    ),
                    mating="POWER",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        )
        for interface_id, pin_number in (("usb-power", "2"), ("serial-power", "5"))
    }


def connector_supply_role_reviews() -> tuple[ConnectorInterfaceReview, ...]:
    return (
        ConnectorInterfaceReview(
            reference="J1",
            disposition="interface",
            basis="Synthetic USB power contact reviewed",
            interface_id="usb-power",
            pin_map={"2": "2"},
        ),
        ConnectorInterfaceReview(
            reference="J2",
            disposition="interface",
            basis="Synthetic serial power contact reviewed",
            interface_id="serial-power",
            pin_map={"5": "5"},
        ),
    )


def three_connector_supply_role_netlist(*, all_common: bool = False) -> NetlistContract:
    nets = (
        {"SHARED_SUPPLY": ("J1.2", "J2.5", "J3.9")}
        if all_common
        else {"SUPPLY_A": ("J1.2", "J2.5"), "SUPPLY_B": ("J3.9",)}
    )
    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={
            "J1": "Synthetic:UsbPort",
            "J2": "Synthetic:SerialPort",
            "J3": "Synthetic:SensorPort",
        },
        component_pin_numbers={"J1": ("2",), "J2": ("5",), "J3": ("9",)},
        pin_functions={"J1.2": "2", "J2.5": "Pin_5", "J3.9": "9"},
    )


def three_connector_supply_role_catalog(
    *, sensor_voltage_domain: str = "external-5v"
) -> dict[str, InterfaceRecord]:
    return {
        **connector_supply_role_catalog(),
        "sensor-power": InterfaceRecord(
            id="sensor-power",
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="9",
                    signal="POWER",
                    role="supply",
                    direction="passive",
                    voltage_domain=sensor_voltage_domain,
                    mating="POWER",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        ),
    }


def three_connector_supply_role_reviews() -> tuple[ConnectorInterfaceReview, ...]:
    return (
        *connector_supply_role_reviews(),
        ConnectorInterfaceReview(
            reference="J3",
            disposition="interface",
            basis="Synthetic sensor power contact reviewed",
            interface_id="sensor-power",
            pin_map={"9": "9"},
        ),
    )


class ConnectorCoverageTests(unittest.TestCase):
    def test_standard_connector_symbol_identity_finds_nonstandard_reference_candidates(
        self,
    ) -> None:
        observed = NetlistContract(
            components={},
            nets={},
            component_symbols={
                "EXT1": "Connector:USB_C_Receptacle_USB2.0_16P",
                "HDR1": "Connector_Generic_MountingPin:Conn_01x02_MountingPin",
                "J1": "Device:R",
                "U7": "Connector_Generic:Conn_01x02",
                "U8": "Connector:TestPoint_Alt",
                "U9": "Device:R",
            },
        )

        coverage = evaluate(observed, (), ())

        self.assertEqual(
            tuple(item.reference for item in coverage.entries), ("EXT1", "HDR1", "J1", "U7")
        )
        self.assertEqual(coverage.status, "UNDECLARED")
        self.assertNotIn("U8", {item.reference for item in coverage.entries})
        self.assertNotIn("U9", {item.reference for item in coverage.entries})

    def test_standard_test_point_library_control_does_not_create_connector_coverage(self) -> None:
        observed = NetlistContract(
            components={},
            nets={},
            component_symbols={
                "U1": "Connector:TestPoint_2Pole",
                "TP1": "TestPoint:TestPoint_Pad_1.5x1.5mm",
                "R1": "Device:R",
            },
        )

        coverage = evaluate(observed, (), (), inventory_review=inventory_review())

        self.assertEqual(coverage.status, "COMPLETE")
        self.assertEqual(coverage.entries, ())

    def test_unreviewed_candidate_is_a_coverage_gap_and_keeps_lint_at_review(self) -> None:
        coverage = evaluate(observed_connector(), (), ())
        self.assertEqual(coverage.status, "UNDECLARED")
        self.assertEqual(coverage.entries[0].reference, "J1")
        self.assertEqual(coverage.entries[0].status, "UNDECLARED")
        report = evaluate_design_lint(
            "synthetic",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic",
                observed=observed_connector(),
            ),
            DesignLintPolicy(),
            connector_coverage=coverage,
        )
        self.assertEqual(report.status, "REVIEW")
        self.assertIn("Connector coverage: UNDECLARED", text_report(report))
        self.assertIn("UNDECLARED connector J1", text_report(report))

    def test_complete_interface_review_accounts_for_every_catalog_and_symbol_pin(self) -> None:
        review = ConnectorInterfaceReview(
            reference="J1",
            disposition="interface",
            basis="Synthetic interface pinout reviewed",
            interface_id="debug-port",
            pin_map={"1": "1", "2": "2"},
            unlisted_pin_reasons={"3": "Synthetic shield pin reviewed separately"},
        )
        coverage = evaluate(
            observed_connector(),
            ("debug-port",),
            (review,),
            interfaces={"debug-port": interface_record()},
            inventory_review=inventory_review(),
        )
        self.assertEqual(coverage.status, "COMPLETE")
        self.assertEqual(coverage.entries[0].status, "COVERED")
        self.assertEqual(coverage.unbound_interface_ids, ())
        self.assertEqual(
            coverage.inventory_review_basis,
            "Synthetic review covered the complete schematic symbol inventory",
        )
        self.assertEqual(coverage.entries[0].interface_pin_map, {"1": "1", "2": "2"})
        self.assertEqual(coverage.entries[0].mapped_pins[0].interface_signal, "TX")
        self.assertEqual(coverage.entries[0].mapped_pins[0].nets, ("TX",))
        self.assertEqual(
            coverage.entries[0].unlisted_pin_reasons,
            {"3": "Synthetic shield pin reviewed separately"},
        )

    def test_reviewed_custom_symbol_discovers_exact_symbol_peers_for_coverage(self) -> None:
        observed = NetlistContract(
            components={},
            nets={"RETURN": ("A1.1", "A2.1"), "OTHER": ("A3.1",)},
            component_symbols={
                "A1": "Synthetic:CustomPort",
                "A2": "Synthetic:CustomPort",
                "A3": "Synthetic:DifferentPort",
            },
            component_pin_numbers={
                "A1": ("1",),
                "A2": ("1",),
                "A3": ("1",),
            },
            pin_functions={"A1.1": "Pin_1", "A2.1": "Pin_1", "A3.1": "Pin_1"},
        )
        interface = InterfaceRecord(
            id="custom-port",
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="1",
                    signal="RETURN",
                    role="return",
                    direction="passive",
                    voltage_domain="signal-return",
                    mating="RETURN",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        )
        review = ConnectorInterfaceReview(
            reference="A1",
            disposition="interface",
            basis="Synthetic custom connector pinout was reviewed",
            interface_id="custom-port",
            pin_map={"1": "1"},
        )

        coverage = evaluate(
            observed,
            ("custom-port",),
            (review,),
            interfaces={"custom-port": interface},
            inventory_review=inventory_review(),
        )

        self.assertEqual(
            {item.reference: item.status for item in coverage.entries},
            {"A1": "COVERED", "A2": "UNDECLARED"},
        )
        self.assertEqual(coverage.status, "UNDECLARED")

        reordered = observed.model_copy(
            update={
                "nets": dict(reversed(tuple(observed.nets.items()))),
                "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(observed.component_pin_numbers.items()))
                ),
                "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            }
        )
        reordered_coverage = evaluate(
            reordered,
            ("custom-port",),
            (review,),
            interfaces={"custom-port": interface},
            inventory_review=inventory_review(),
        )
        self.assertEqual(reordered_coverage, coverage)

        not_applicable = ConnectorInterfaceReview(
            reference="A2",
            disposition="not_applicable",
            basis="Synthetic instance is a local fixture connector",
        )
        dispositioned = evaluate(
            observed,
            ("custom-port",),
            (review, not_applicable),
            interfaces={"custom-port": interface},
            inventory_review=inventory_review(),
        )
        self.assertEqual(dispositioned.status, "COMPLETE")
        self.assertEqual(
            {item.reference: item.status for item in dispositioned.entries},
            {"A1": "COVERED", "A2": "NOT_APPLICABLE"},
        )

    def test_reviewed_supply_domains_compare_generic_contacts_across_symbols(self) -> None:
        split = connector_supply_role_netlist()
        baseline = evaluate_design_lint(
            "synthetic-generic-supply-split-baseline",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-generic-supply-split-baseline",
                observed=split,
                netlist_sha256="1" * 64,
            ),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "connector.repeated_pin_function",
            {finding.rule_id for finding in baseline.findings},
        )

        coverage = evaluate(
            split,
            ("usb-power", "serial-power"),
            connector_supply_role_reviews(),
            interfaces=connector_supply_role_catalog(),
            interface_catalog_path="catalog/interfaces.json",
            interface_catalog_sha256="2" * 64,
            inventory_review=inventory_review(),
        )
        self.assertEqual(coverage.status, "COMPLETE")
        mapped_supply = next(pin for entry in coverage.entries for pin in entry.mapped_pins)
        self.assertEqual(mapped_supply.voltage_domain, "external-5v")

        fault = evaluate_design_lint(
            "synthetic-generic-supply-split",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-generic-supply-split",
                observed=split,
                netlist_sha256="3" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=coverage,
        )
        self.assertEqual(fault.status, "REVIEW")
        self.assertEqual(
            {finding.rule_id for finding in fault.findings},
            {"connector.repeated_pin_function"},
        )
        finding = fault.findings[0]
        self.assertEqual(
            dict(finding.evidence),
            {
                "J1.2": ("NODE_ALPHA",),
                "J2.5": ("NODE_BETA",),
                "role_classification_sources": (
                    (
                        "J1.2: project interface catalog role=supply; "
                        "voltage_domain=external-5v; native symbol function=2"
                    ),
                    (
                        "J2.5: project interface catalog role=supply; "
                        "voltage_domain=external-5v; native symbol function=Pin_5"
                    ),
                ),
                "reviewed_voltage_domain": ("external-5v",),
            },
        )
        self.assertIn("does not require commonality", finding.message)

        open_supply = connector_supply_role_netlist(open_supply=True)
        open_supply_coverage = evaluate(
            open_supply,
            ("usb-power", "serial-power"),
            connector_supply_role_reviews(),
            interfaces=connector_supply_role_catalog(),
            interface_catalog_path="catalog/interfaces.json",
            interface_catalog_sha256="9" * 64,
            inventory_review=inventory_review(),
        )
        self.assertEqual(open_supply_coverage.status, "COMPLETE")
        open_supply_report = evaluate_design_lint(
            "synthetic-generic-supply-open-contact",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-generic-supply-open-contact",
                observed=open_supply,
                netlist_sha256="a" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=open_supply_coverage,
        )
        self.assertEqual(open_supply_report.status, "REVIEW")
        self.assertEqual(
            {item.rule_id for item in open_supply_report.findings},
            {"connector.repeated_pin_function"},
            "the cross-symbol role finding reports the open contact without a duplicate prompt",
        )
        open_supply_finding = open_supply_report.findings[0]
        self.assertEqual(open_supply_finding.evidence["J1.2"], ("NODE_ALPHA",))
        self.assertEqual(open_supply_finding.evidence["J2.5"], ())
        self.assertIn("does not require commonality", open_supply_finding.message)

        reordered = split.model_copy(
            update={
                "nets": dict(reversed(tuple(split.nets.items()))),
                "component_symbols": dict(reversed(tuple(split.component_symbols.items()))),
                "component_pin_numbers": dict(reversed(tuple(split.component_pin_numbers.items()))),
                "pin_functions": dict(reversed(tuple(split.pin_functions.items()))),
            }
        )
        reordered_coverage = evaluate(
            reordered,
            ("usb-power", "serial-power"),
            connector_supply_role_reviews(),
            interfaces=connector_supply_role_catalog(),
            interface_catalog_path="catalog/interfaces.json",
            interface_catalog_sha256="2" * 64,
            inventory_review=inventory_review(),
        )
        reordered_fault = evaluate_design_lint(
            "synthetic-generic-supply-split",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-generic-supply-split",
                observed=reordered,
                netlist_sha256="8" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=reordered_coverage,
        )
        self.assertNotEqual(fault.netlist_sha256, reordered_fault.netlist_sha256)
        self.assertEqual(reordered_fault.status, fault.status)
        self.assertEqual(
            tuple(
                (item.rule_id, item.subject, item.message, item.evidence, item.fingerprint)
                for item in reordered_fault.findings
            ),
            tuple(
                (item.rule_id, item.subject, item.message, item.evidence, item.fingerprint)
                for item in fault.findings
            ),
        )

        common = connector_supply_role_netlist(common_supply=True)
        common_report = evaluate_design_lint(
            "synthetic-generic-supply-common-control",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-generic-supply-common-control",
                observed=common,
                netlist_sha256="4" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=evaluate(
                common,
                ("usb-power", "serial-power"),
                connector_supply_role_reviews(),
                interfaces=connector_supply_role_catalog(),
                interface_catalog_path="catalog/interfaces.json",
                interface_catalog_sha256="5" * 64,
                inventory_review=inventory_review(),
            ),
        )
        self.assertEqual(common_report.status, "PASS")
        self.assertFalse(common_report.findings)

        separate_domains = evaluate_design_lint(
            "synthetic-generic-supply-domain-control",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-generic-supply-domain-control",
                observed=split,
                netlist_sha256="6" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=evaluate(
                split,
                ("usb-power", "serial-power"),
                connector_supply_role_reviews(),
                interfaces=connector_supply_role_catalog(serial_voltage_domain="isolated-5v"),
                interface_catalog_path="catalog/interfaces.json",
                interface_catalog_sha256="7" * 64,
                inventory_review=inventory_review(),
            ),
        )
        self.assertEqual(separate_domains.status, "PASS")
        self.assertFalse(separate_domains.findings)

    def test_three_mapped_supply_peers_localize_one_split_from_two_common(self) -> None:
        def coverage(
            observed: NetlistContract, *, sensor_domain: str = "external-5v"
        ) -> ConnectorCoverageReport:
            return evaluate(
                observed,
                ("usb-power", "serial-power", "sensor-power"),
                three_connector_supply_role_reviews(),
                interfaces=three_connector_supply_role_catalog(sensor_voltage_domain=sensor_domain),
                interface_catalog_path="catalog/interfaces.json",
                interface_catalog_sha256="8" * 64,
                inventory_review=inventory_review(),
            )

        split = three_connector_supply_role_netlist()
        split_coverage = coverage(split)
        self.assertEqual(split_coverage.status, "COMPLETE")
        self.assertTrue(all(entry.status == "COVERED" for entry in split_coverage.entries))
        baseline = evaluate_design_lint(
            "synthetic-three-connector-supply-baseline",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-three-connector-supply-baseline",
                observed=split,
                netlist_sha256="9" * 64,
            ),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "connector.repeated_pin_function",
            {finding.rule_id for finding in baseline.findings},
        )

        fault = evaluate_design_lint(
            "synthetic-three-connector-supply-split",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-three-connector-supply-split",
                observed=split,
                netlist_sha256="a" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=split_coverage,
        )
        self.assertEqual(fault.status, "REVIEW")
        self.assertEqual(len(fault.findings), 1)
        finding = fault.findings[0]
        self.assertEqual(finding.rule_id, "connector.repeated_pin_function")
        self.assertEqual(
            {key: finding.evidence[key] for key in ("J1.2", "J2.5", "J3.9")},
            {
                "J1.2": ("SUPPLY_A",),
                "J2.5": ("SUPPLY_A",),
                "J3.9": ("SUPPLY_B",),
            },
        )
        self.assertEqual(finding.evidence["reviewed_voltage_domain"], ("external-5v",))
        self.assertIn("does not require commonality", finding.message)

        common = three_connector_supply_role_netlist(all_common=True)
        common_report = evaluate_design_lint(
            "synthetic-three-connector-supply-common",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-three-connector-supply-common",
                observed=common,
                netlist_sha256="b" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=coverage(common),
        )
        self.assertEqual(common_report.status, "PASS")
        self.assertFalse(common_report.findings)

        independent_domain_report = evaluate_design_lint(
            "synthetic-three-connector-independent-supply",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-three-connector-independent-supply",
                observed=split,
                netlist_sha256="c" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=coverage(split, sensor_domain="isolated-5v"),
        )
        self.assertEqual(independent_domain_report.status, "PASS")
        self.assertFalse(independent_domain_report.findings)

    def test_mapped_generic_peer_roles_suppress_duplicate_pin_divergence(self) -> None:
        observed = NetlistContract(
            components={},
            nets={
                "SUPPLY_A": ("J1.1",),
                "SUPPLY_B": ("J2.1",),
                "GND": ("J1.2", "J2.2"),
            },
            component_symbols={"J1": "Synthetic:PeerPort", "J2": "Synthetic:PeerPort"},
            component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
            pin_functions={
                "J1.1": "Pin_1",
                "J2.1": "Pin_1",
                "J1.2": "GND",
                "J2.2": "GND",
            },
        )
        interface = InterfaceRecord(
            id="peer-port",
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="1",
                    signal="POWER",
                    role="supply",
                    direction="passive",
                    voltage_domain="external-5v",
                    mating="POWER",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
                InterfacePin(
                    number="2",
                    signal="RETURN",
                    role="return",
                    direction="passive",
                    voltage_domain="signal-return",
                    mating="RETURN",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        )
        reviews = tuple(
            ConnectorInterfaceReview(
                reference=reference,
                disposition="interface",
                basis="Synthetic peer connector pinout was reviewed",
                interface_id="peer-port",
                pin_map={"1": "1", "2": "2"},
            )
            for reference in ("J1", "J2")
        )
        coverage = evaluate(
            observed,
            ("peer-port",),
            reviews,
            interfaces={"peer-port": interface},
            interface_catalog_path="catalog/interfaces.json",
            interface_catalog_sha256="d" * 64,
            inventory_review=inventory_review(),
        )
        report = evaluate_design_lint(
            "synthetic-mapped-peer-pin-divergence",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-mapped-peer-pin-divergence",
                observed=observed,
                netlist_sha256="e" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=coverage,
        )

        self.assertEqual(
            {finding.rule_id for finding in report.findings},
            {"connector.repeated_pin_function"},
        )
        self.assertEqual(report.findings[0].evidence["J1.1"], ("SUPPLY_A",))
        self.assertEqual(report.findings[0].evidence["J2.1"], ("SUPPLY_B",))

        partial_observed = observed.model_copy(
            update={
                "nets": {
                    "SUPPLY_A": ("J1.1", "J3.1"),
                    "SUPPLY_B": ("J2.1",),
                    "GND": ("J1.2", "J2.2", "J3.2"),
                },
                "component_symbols": {
                    **observed.component_symbols,
                    "J3": "Synthetic:PeerPort",
                },
                "component_pin_numbers": {
                    **observed.component_pin_numbers,
                    "J3": ("1", "2"),
                },
                "pin_functions": {
                    **observed.pin_functions,
                    "J3.1": "Pin_1",
                    "J3.2": "GND",
                },
            }
        )
        partial_coverage = evaluate(
            partial_observed,
            ("peer-port",),
            reviews,
            interfaces={"peer-port": interface},
            interface_catalog_path="catalog/interfaces.json",
            interface_catalog_sha256="d" * 64,
            inventory_review=inventory_review(),
        )
        partial_report = evaluate_design_lint(
            "synthetic-partial-mapped-peer-pin-divergence",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-partial-mapped-peer-pin-divergence",
                observed=partial_observed,
                netlist_sha256="f" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=partial_coverage,
        )
        generic_finding = next(
            finding
            for finding in partial_report.findings
            if finding.rule_id == "connector.peer_pin_assignment_outlier"
        )
        self.assertEqual(partial_coverage.status, "UNDECLARED")
        self.assertEqual(
            next(entry.status for entry in partial_coverage.entries if entry.reference == "J3"),
            "UNDECLARED",
        )
        self.assertIn(
            "connector.repeated_pin_function",
            {finding.rule_id for finding in partial_report.findings},
        )
        self.assertEqual(generic_finding.evidence["outlier_pins"], ("J2.1",))
        self.assertEqual(generic_finding.evidence["J3.1"], ("SUPPLY_A",))

    def test_peer_assignment_groups_scope_generic_pins_but_keep_return_review_global(
        self,
    ) -> None:
        with self.assertRaises(ValidationError):
            ConnectorInterfaceReview(
                reference="J1",
                disposition="interface",
                basis="Reviewed J1's interface pinout",
                interface_id="uart-header-1",
                pin_map={"1": "1"},
                peer_assignment_group="uart-1",
            )

        split = uart_peer_netlist(split_return=True)
        separate_groups = uart_header_coverage(split, groups=("uart-1", "uart-2"))
        self.assertEqual(
            source_matched_connector_peer_assignment_groups(split, separate_groups),
            {
                "J1": (
                    "uart-1",
                    "Reviewed J1 as a member of peer-assignment group uart-1",
                ),
                "J2": (
                    "uart-2",
                    "Reviewed J2 as a member of peer-assignment group uart-2",
                ),
            },
        )
        separate_report = evaluate_design_lint(
            "synthetic-separate-uart-peer-groups",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-separate-uart-peer-groups",
                observed=split,
                netlist_sha256="b" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=separate_groups,
        )
        self.assertFalse(
            {
                finding.rule_id
                for finding in separate_report.findings
                if finding.rule_id
                in {
                    "connector.peer_pin_assignment_outlier",
                    "connector.peer_pin_assignment_divergence",
                }
            }
        )
        return_finding = next(
            finding
            for finding in separate_report.findings
            if finding.rule_id == "connector.repeated_pin_function"
        )
        self.assertEqual(return_finding.evidence["J1.3"], ("UART1_RETURN",))
        self.assertEqual(return_finding.evidence["J2.3"], ("UART2_RETURN",))

        supply_netlist = NetlistContract(
            components={},
            nets={"PORT1_3V3": ("J1.2",), "PORT2_3V3": ("J2.2",)},
            component_symbols={
                "J1": "Connector_Generic:Conn_01x02",
                "J2": "Connector_Generic:Conn_01x02",
            },
            component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
            pin_functions={"J1.1": "Pin_1", "J1.2": "Pin_2", "J2.1": "Pin_1", "J2.2": "Pin_2"},
        )
        supply_interface = InterfaceRecord(
            id="two-pin-supply",
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="1",
                    signal="SIGNAL",
                    role="signal",
                    direction="bidirectional",
                    voltage_domain="logic-3v3",
                    mating="SIGNAL",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
                InterfacePin(
                    number="2",
                    signal="3V3",
                    role="supply",
                    direction="power_out",
                    voltage_domain="logic-3v3",
                    mating="3V3",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        )
        supply_reviews = tuple(
            ConnectorInterfaceReview(
                reference=reference,
                disposition="interface",
                basis=f"Reviewed {reference} supply interface",
                interface_id="two-pin-supply",
                pin_map={"1": "1", "2": "2"},
                peer_assignment_group=group,
                peer_assignment_basis=f"Reviewed {reference} in group {group}",
            )
            for reference, group in (("J1", "power-domain-1"), ("J2", "power-domain-2"))
        )
        supply_coverage = evaluate(
            supply_netlist,
            ("two-pin-supply",),
            supply_reviews,
            interfaces={"two-pin-supply": supply_interface},
            interface_catalog_path="catalog/interfaces.json",
            interface_catalog_sha256="f" * 64,
            inventory_review=inventory_review(),
        )
        supply_report = evaluate_design_lint(
            "synthetic-cross-group-supply-review",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-cross-group-supply-review",
                observed=supply_netlist,
                netlist_sha256="f" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=supply_coverage,
        )
        supply_finding = next(
            finding
            for finding in supply_report.findings
            if finding.rule_id == "connector.repeated_pin_function"
        )
        self.assertEqual(supply_finding.evidence["J1.2"], ("PORT1_3V3",))
        self.assertEqual(supply_finding.evidence["J2.2"], ("PORT2_3V3",))

        same_group = uart_header_coverage(split, groups=("uart-ports", "uart-ports"))
        same_group_report = evaluate_design_lint(
            "synthetic-same-uart-peer-group",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-same-uart-peer-group",
                observed=split,
                netlist_sha256="c" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=same_group,
        )
        generic_findings = tuple(
            finding
            for finding in same_group_report.findings
            if finding.rule_id == "connector.peer_pin_assignment_divergence"
        )
        self.assertEqual(len(generic_findings), 2)
        self.assertTrue(
            all(
                finding.evidence["peer_assignment_group"] == ("uart-ports",)
                for finding in generic_findings
            )
        )
        self.assertTrue(
            all("peer-assignment group" in finding.message for finding in generic_findings)
        )
        expected_peer_basis = (
            "J1: uart-ports; Reviewed J1 as a member of peer-assignment group uart-ports",
            "J2: uart-ports; Reviewed J2 as a member of peer-assignment group uart-ports",
        )
        self.assertTrue(
            all(
                finding.evidence["peer_assignment_basis"] == expected_peer_basis
                for finding in generic_findings
            )
        )
        rendered = text_report(same_group_report)
        self.assertIn("Peer-assignment group: uart-ports", rendered)
        self.assertIn("Peer-assignment basis: Reviewed J1 as a member", rendered)

        outlier_netlist = NetlistContract(
            components={},
            nets={"UART1_TX": ("J1.1", "J2.1"), "UART2_TX": ("J3.1",)},
            component_symbols={
                reference: "Synthetic:PeripheralPort" for reference in ("J1", "J2", "J3")
            },
            component_pin_numbers={reference: ("1",) for reference in ("J1", "J2", "J3")},
            pin_functions={f"J{index}.1": "Pin_1" for index in (1, 2, 3)},
        )
        self.assertEqual(
            connector_peer_pin_assignment_outliers(outlier_netlist)[0].outlier_pins,
            ("J3.1",),
        )
        self.assertFalse(
            connector_peer_pin_assignment_outliers(
                outlier_netlist,
                peer_assignment_groups={
                    "J1": ("uart-1", "Reviewed UART1 peer pins"),
                    "J2": ("uart-1", "Reviewed UART1 peer pins"),
                    "J3": ("uart-2", "Reviewed UART2 peer pins"),
                },
            )
        )

        incomplete = evaluate(
            split,
            ("uart-header-1",),
            (
                ConnectorInterfaceReview(
                    reference="J1",
                    disposition="interface",
                    basis="Reviewed J1 as a 3.3 V UART interface",
                    interface_id="uart-header-1",
                    pin_map={"1": "1", "2": "2", "3": "3"},
                    peer_assignment_group="uart-1",
                    peer_assignment_basis="Reviewed J1's comparison group",
                ),
            ),
            interfaces={"uart-header-1": uart_header_interface("uart-header-1")},
            interface_catalog_path="catalog/interfaces.json",
            interface_catalog_sha256="a" * 64,
            inventory_review=inventory_review(),
        )
        incomplete_report = evaluate_design_lint(
            "synthetic-incomplete-uart-peer-groups",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-incomplete-uart-peer-groups",
                observed=split,
                netlist_sha256="d" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=incomplete,
        )
        self.assertTrue(
            any(
                finding.rule_id == "connector.peer_pin_assignment_divergence"
                for finding in incomplete_report.findings
            ),
            "an unreviewed peer keeps the conservative comparison active",
        )

        changed_nets = dict(split.nets)
        changed_nets.pop("UART2_TX")
        changed_nets["UART2_TX_CHANGED"] = ("J2.1",)
        changed = split.model_copy(update={"nets": changed_nets})
        self.assertEqual(
            set(source_matched_connector_peer_assignment_groups(changed, separate_groups)),
            {"J1"},
        )
        stale_report = evaluate_design_lint(
            "synthetic-stale-uart-peer-group",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-stale-uart-peer-group",
                observed=changed,
                netlist_sha256="e" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=separate_groups,
        )
        self.assertTrue(
            any(
                finding.rule_id == "connector.peer_pin_assignment_divergence"
                for finding in stale_report.findings
            ),
            "a source mismatch cannot silence the generic peer comparison",
        )

    def test_peer_groups_scope_generic_pins_while_mapped_returns_remain_global(self) -> None:
        interface = InterfaceRecord(
            id="peer-return",
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="2",
                    signal="RETURN",
                    role="return",
                    direction="bidirectional",
                    voltage_domain="signal-return",
                    mating="RETURN",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        )

        def peer_netlist(*, split_returns: bool, split_signals: bool) -> NetlistContract:
            signal_nets = (
                ("SIGNAL_A", "SIGNAL_B", "SIGNAL_C")
                if split_signals
                else ("SIGNAL", "SIGNAL", "SIGNAL")
            )
            return_nets = (
                ("RETURN_A", "RETURN_B", "RETURN_C") if split_returns else ("GND", "GND", "GND")
            )
            nets: dict[str, tuple[str, ...]] = {}
            for index, net in enumerate(signal_nets, start=1):
                nets.setdefault(net, ())
                nets[net] = (*nets[net], f"J{index}.1")
            for index, net in enumerate(return_nets, start=1):
                nets.setdefault(net, ())
                nets[net] = (*nets[net], f"J{index}.2")
            return NetlistContract(
                components={},
                nets=nets,
                component_symbols={f"J{index}": "Lint:PeerPowerPort" for index in range(1, 4)},
                component_pin_numbers={f"J{index}": ("1", "2") for index in range(1, 4)},
                pin_functions={
                    **{f"J{index}.1": "Pin_1" for index in range(1, 4)},
                    **{f"J{index}.2": "GND" for index in range(1, 4)},
                },
            )

        def mapped_coverage(
            observed: NetlistContract, *, shared_group: bool
        ) -> ConnectorCoverageReport:
            reviews = tuple(
                ConnectorInterfaceReview(
                    reference=f"J{index}",
                    disposition="interface",
                    basis=f"Reviewed J{index} return contact against the synthetic pinout",
                    interface_id="peer-return",
                    pin_map={"2": "2"},
                    unlisted_pin_reasons={
                        "1": "Generic Pin_1 signal contact has no reviewed role in this fixture"
                    },
                    peer_assignment_group="uart-peers" if shared_group else f"uart-{index}",
                    peer_assignment_basis=(
                        "Reviewed matching generic signal contacts as one UART peer set"
                        if shared_group
                        else f"Reviewed J{index} as an independent UART interface"
                    ),
                )
                for index in range(1, 4)
            )
            return evaluate(
                observed,
                ("peer-return",),
                reviews,
                interfaces={"peer-return": interface},
                interface_catalog_path="catalog/interfaces.json",
                interface_catalog_sha256="f" * 64,
                inventory_review=inventory_review(),
            )

        split = peer_netlist(split_returns=True, split_signals=True)
        separate_coverage = mapped_coverage(split, shared_group=False)
        self.assertEqual(separate_coverage.status, "COMPLETE")
        separate_report = evaluate_design_lint(
            "synthetic-peer-groups-split-return",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-peer-groups-split-return",
                observed=split,
                netlist_sha256="a" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=separate_coverage,
        )
        separate_rule_ids = {finding.rule_id for finding in separate_report.findings}
        self.assertEqual(separate_rule_ids, {"connector.repeated_pin_function"})
        return_finding = separate_report.findings[0]
        self.assertEqual(
            {pin: return_finding.evidence[pin] for pin in ("J1.2", "J2.2", "J3.2")},
            {
                "J1.2": ("RETURN_A",),
                "J2.2": ("RETURN_B",),
                "J3.2": ("RETURN_C",),
            },
        )

        shared_coverage = mapped_coverage(split, shared_group=True)
        shared_report = evaluate_design_lint(
            "synthetic-peer-groups-shared-signals",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-peer-groups-shared-signals",
                observed=split,
                netlist_sha256="a" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=shared_coverage,
        )
        shared_findings = {finding.rule_id: finding for finding in shared_report.findings}
        self.assertEqual(
            set(shared_findings),
            {"connector.repeated_pin_function", "connector.peer_pin_assignment_divergence"},
        )
        divergence = shared_findings["connector.peer_pin_assignment_divergence"]
        self.assertEqual(divergence.evidence["peer_assignment_group"], ("uart-peers",))
        self.assertEqual(len(divergence.evidence["peer_assignment_basis"]), 3)
        self.assertEqual(
            {
                pin: shared_findings["connector.repeated_pin_function"].evidence[pin]
                for pin in ("J1.2", "J2.2", "J3.2")
            },
            {
                "J1.2": ("RETURN_A",),
                "J2.2": ("RETURN_B",),
                "J3.2": ("RETURN_C",),
            },
            "a shared signal peer group must not scope away cross-port return review",
        )

        control = peer_netlist(split_returns=False, split_signals=False)
        control_report = evaluate_design_lint(
            "synthetic-peer-groups-common-control",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-peer-groups-common-control",
                observed=control,
                netlist_sha256="b" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=mapped_coverage(control, shared_group=True),
        )
        self.assertEqual(control_report.status, "PASS")
        self.assertEqual(control_report.findings, ())

    def test_peer_assignment_scope_reports_are_stable_under_input_reordering(self) -> None:
        observed = uart_peer_netlist(split_return=True)
        reordered = observed.model_copy(
            update={
                "nets": dict(reversed(tuple(observed.nets.items()))),
                "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
                "component_pin_numbers": {
                    reference: tuple(reversed(pin_numbers))
                    for reference, pin_numbers in reversed(
                        tuple(observed.component_pin_numbers.items())
                    )
                },
                "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            }
        )

        for groups in (("uart-1", "uart-2"), ("uart-ports", "uart-ports")):
            with self.subTest(groups=groups):
                reports = tuple(
                    evaluate_design_lint(
                        "synthetic-peer-assignment-order",
                        ContractCoachReport(
                            status="READY_FOR_REVIEW",
                            project_id="synthetic-peer-assignment-order",
                            observed=netlist,
                            netlist_sha256="f" * 64,
                        ),
                        DesignLintPolicy(),
                        connector_coverage=uart_header_coverage(
                            netlist,
                            groups=groups,
                            reverse_inputs=reverse_inputs,
                        ),
                    ).model_dump(mode="json")
                    for netlist, reverse_inputs in (
                        (observed, False),
                        (reordered, True),
                    )
                )
                self.assertEqual(reports[0], reports[1])

    def test_reviewed_return_roles_refine_connector_net_heuristics(self) -> None:
        def role_coverage(
            netlist: NetlistContract,
            *,
            catalog_sha256: str | None = "b" * 64,
        ) -> ConnectorCoverageReport:
            return evaluate(
                netlist,
                ("usb-interface", "serial-interface"),
                connector_return_role_reviews(),
                interfaces=connector_return_role_catalog(),
                interface_catalog_path="catalog/interfaces.json",
                interface_catalog_sha256=catalog_sha256,
                inventory_review=inventory_review(),
            )

        split = connector_return_role_netlist()
        split_coverage = role_coverage(split)
        self.assertEqual(split_coverage.status, "COMPLETE")
        self.assertEqual(
            next(entry for entry in split_coverage.entries if entry.reference == "J2")
            .mapped_pins[2]
            .role,
            "return",
        )

        split_report = evaluate_design_lint(
            "synthetic-reviewed-return-split",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-reviewed-return-split",
                observed=split,
                netlist_sha256="a" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=split_coverage,
        )
        self.assertEqual(split_report.status, "REVIEW")
        return_finding = next(
            finding
            for finding in split_report.findings
            if finding.rule_id == "connector.repeated_pin_function"
        )
        self.assertEqual(
            dict(return_finding.evidence),
            {
                "J1.3": ("USB_RETURN",),
                "J2.3": ("SERIAL_RETURN",),
                "role_classification_sources": (
                    "J1.3: project interface catalog role=return; native symbol function=GND",
                    "J2.3: project interface catalog role=return; native symbol function=Pin_3",
                ),
            },
        )
        self.assertIn(
            "role classification alone does not require commonality", return_finding.message
        )
        rendered_split = text_report(split_report)
        self.assertIn(
            f"Interface catalog: catalog/interfaces.json ({'b' * 64})",
            rendered_split,
        )
        self.assertIn(
            "role_classification_sources: J1.3: project interface catalog role=return; "
            "native symbol function=GND, "
            "J2.3: project interface catalog role=return; native symbol function=Pin_3",
            rendered_split,
        )
        self.assertIn("Interface pin 3 (RETURN) maps to J2.3: role=return", rendered_split)
        self.assertNotIn(
            "connector.no_connected_return",
            {finding.rule_id for finding in split_report.findings},
        )

        source_interfaces = connector_return_role_catalog()
        reordered_interfaces = {
            interface_id: interface.model_copy(update={"pins": tuple(reversed(interface.pins))})
            for interface_id, interface in reversed(tuple(source_interfaces.items()))
        }
        reordered_reviews = tuple(
            review.model_copy(
                update={
                    "pin_map": dict(reversed(tuple(review.pin_map.items()))),
                    "unlisted_pin_reasons": dict(
                        reversed(tuple(review.unlisted_pin_reasons.items()))
                    ),
                }
            )
            for review in reversed(connector_return_role_reviews())
        )
        reordered_coverage = evaluate(
            split,
            ("serial-interface", "usb-interface"),
            reordered_reviews,
            interfaces=reordered_interfaces,
            interface_catalog_path="catalog/interfaces.json",
            interface_catalog_sha256="b" * 64,
            inventory_review=inventory_review(),
        )
        reordered_report = evaluate_design_lint(
            "synthetic-reviewed-return-split",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-reviewed-return-split",
                observed=split,
                netlist_sha256="a" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=reordered_coverage,
        )
        self.assertEqual(reordered_coverage, split_coverage)
        self.assertEqual(reordered_report, split_report)

        disabled_report = evaluate_design_lint(
            "synthetic-reviewed-return-split-disabled",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-reviewed-return-split-disabled",
                observed=split,
                netlist_sha256="a" * 64,
            ),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.repeated_pin_function",
                        mode="off",
                        reason="Synthetic project intentionally isolates these interface returns",
                    ),
                )
            ),
            connector_coverage=split_coverage,
        )
        self.assertEqual(disabled_report.status, "PASS")
        self.assertEqual(len(disabled_report.findings), 1)
        self.assertEqual(disabled_report.findings[0].mode, "off")
        self.assertEqual(disabled_report.findings[0].disposition, "RULE_OFF")

        unbound_catalog_report = evaluate_design_lint(
            "synthetic-unbound-return-catalog",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-unbound-return-catalog",
                observed=split,
                netlist_sha256="b" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=role_coverage(split, catalog_sha256=None),
        )
        self.assertIn(
            "connector.no_connected_return",
            {finding.rule_id for finding in unbound_catalog_report.findings},
        )

        incomplete_coverage = split_coverage.model_copy(
            update={
                "status": "INCOMPLETE",
                "entries": tuple(
                    entry.model_copy(update={"status": "INCOMPLETE"})
                    for entry in split_coverage.entries
                ),
            }
        )
        incomplete_map_report = evaluate_design_lint(
            "synthetic-incomplete-return-map",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-incomplete-return-map",
                observed=split,
                netlist_sha256="b" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=incomplete_coverage,
        )
        self.assertIn(
            "connector.no_connected_return",
            {finding.rule_id for finding in incomplete_map_report.findings},
        )

        common = connector_return_role_netlist(common_return=True)
        common_coverage = role_coverage(common)
        common_report = evaluate_design_lint(
            "synthetic-reviewed-common-return",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-reviewed-common-return",
                observed=common,
                netlist_sha256="c" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=common_coverage,
        )
        self.assertEqual(common_report.status, "PASS")
        self.assertFalse(common_report.findings)

        open_return = connector_return_role_netlist(common_return=True, open_return=True)
        open_return_report = evaluate_design_lint(
            "synthetic-reviewed-open-return",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-reviewed-open-return",
                observed=open_return,
                netlist_sha256="e" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=role_coverage(open_return),
        )
        self.assertEqual(open_return_report.status, "REVIEW")
        return_pin_finding = next(
            finding
            for finding in open_return_report.findings
            if finding.rule_id == "connector.repeated_pin_function"
        )
        self.assertEqual(return_pin_finding.evidence["J2.3"], ())
        self.assertNotIn(
            "connector.no_connected_return",
            {finding.rule_id for finding in open_return_report.findings},
        )

        open_supply = connector_return_role_netlist(common_return=True, open_supply=True)
        open_supply_report = evaluate_design_lint(
            "synthetic-reviewed-open-supply",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-reviewed-open-supply",
                observed=open_supply,
                netlist_sha256="f" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=role_coverage(open_supply),
        )
        supply_pin_finding = next(
            finding
            for finding in open_supply_report.findings
            if finding.rule_id == "connector.unconnected_supply_pin"
        )
        self.assertEqual(supply_pin_finding.subject, "J2.4: V+")
        self.assertEqual(
            supply_pin_finding.evidence["role_source"],
            ("project interface catalog",),
        )

        stale_netlist = common.model_copy(
            update={
                "nets": {
                    "COMMON_RETURN": ("J1.3",),
                    "SERIAL_RETURN": ("J2.3",),
                    "USB_DATA_1": ("J1.1",),
                    "USB_DATA_2": ("J1.2",),
                    "SERIAL_TX": ("J2.1",),
                    "SERIAL_RX": ("J2.2",),
                    "SERIAL_SUPPLY": ("J2.4",),
                }
            }
        )
        stale_report = evaluate_design_lint(
            "synthetic-stale-return-coverage",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-stale-return-coverage",
                observed=stale_netlist,
                netlist_sha256="d" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=common_coverage,
        )
        self.assertIn(
            "connector.no_connected_return",
            {finding.rule_id for finding in stale_report.findings},
        )

    def test_missing_and_unknown_catalog_or_symbol_pins_are_named(self) -> None:
        review = ConnectorInterfaceReview(
            reference="J1",
            disposition="interface",
            basis="Synthetic partial interface map",
            interface_id="debug-port",
            pin_map={"1": "1", "stale": "9"},
        )
        coverage = evaluate(
            observed_connector(),
            ("debug-port",),
            (review,),
            interfaces={"debug-port": interface_record()},
        )
        entry = coverage.entries[0]
        self.assertEqual(coverage.status, "INCOMPLETE")
        self.assertEqual(entry.status, "INCOMPLETE")
        self.assertEqual(entry.interface_pins_unmapped, ("2",))
        self.assertEqual(entry.interface_pins_unknown, ("stale",))
        self.assertEqual(entry.component_pins_unaccounted, ("2", "3"))
        self.assertEqual(entry.component_pins_unknown, ("9",))

    def test_explicit_not_applicable_decision_covers_a_candidate_without_joining_nets(self) -> None:
        review = ConnectorInterfaceReview(
            reference="J1",
            disposition="not_applicable",
            basis="Synthetic connector is a local service jumper, not an external interface",
        )
        coverage = evaluate(
            observed_connector(), (), (review,), inventory_review=inventory_review()
        )
        self.assertEqual(coverage.status, "COMPLETE")
        self.assertEqual(coverage.entries[0].status, "NOT_APPLICABLE")

    def test_reviewed_connector_rows_still_need_complete_inventory_scope(self) -> None:
        review = ConnectorInterfaceReview(
            reference="J1",
            disposition="not_applicable",
            basis="Synthetic connector is a local service jumper",
        )
        coverage = evaluate(observed_connector(), (), (review,))
        self.assertEqual(coverage.status, "SCOPE_UNREVIEWED")

    def test_explicit_review_can_cover_a_reference_outside_candidate_prefixes(self) -> None:
        review = ConnectorInterfaceReview(
            reference="EXT1",
            disposition="not_applicable",
            basis="Synthetic external-style reference was reviewed directly",
        )
        observed = NetlistContract(
            components={},
            nets={},
            component_symbols={"EXT1": "Synthetic:DebugConnector"},
            component_pin_numbers={"EXT1": ("1",)},
        )
        coverage = evaluate(observed, (), (review,), inventory_review=inventory_review())
        self.assertEqual(coverage.status, "COMPLETE")
        self.assertEqual(coverage.entries[0].status, "NOT_APPLICABLE")

    def test_stale_review_and_missing_interface_record_are_incomplete(self) -> None:
        stale = ConnectorInterfaceReview(
            reference="J2",
            disposition="not_applicable",
            basis="Synthetic old reference",
        )
        stale_coverage = evaluate(observed_connector(), (), (stale,))
        self.assertEqual(stale_coverage.status, "INCOMPLETE")
        stale_entry = next(entry for entry in stale_coverage.entries if entry.reference == "J2")
        self.assertEqual(stale_entry.status, "STALE")

        review = ConnectorInterfaceReview(
            reference="J1",
            disposition="interface",
            basis="Synthetic missing catalog record",
            interface_id="missing-interface",
            pin_map={"1": "1"},
        )
        missing = evaluate(
            observed_connector(),
            ("missing-interface",),
            (review,),
            interfaces={},
        )
        self.assertEqual(missing.status, "INCOMPLETE")
        self.assertIn("missing-interface", missing.entries[0].issues[0])

    def test_no_candidates_without_declarations_is_explicitly_unassessed(self) -> None:
        observed = observed_connector(candidate=False)
        coverage = evaluate(observed, (), ())
        self.assertEqual(coverage.status, "UNASSESSED")
        self.assertIn("does not prove", coverage.scope)
        report = evaluate_design_lint(
            "synthetic-no-interfaces",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-no-interfaces",
                observed=observed,
                netlist_sha256="a" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=coverage,
        )
        self.assertEqual(report.status, "REVIEW")
        self.assertIn(
            "connector_inventory_review",
            " ".join(report.next_actions),
        )

    def test_explicit_inventory_review_can_confirm_no_external_connectors(self) -> None:
        observed = NetlistContract(components={}, nets={})
        coverage = evaluate(observed, (), (), inventory_review=inventory_review())
        self.assertEqual(coverage.status, "COMPLETE")
        report = evaluate_design_lint(
            "synthetic-no-interfaces",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-no-interfaces",
                observed=observed,
                netlist_sha256="a" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=coverage,
        )
        self.assertEqual(report.status, "PASS")
        self.assertIn(
            "Inventory review basis: Synthetic review covered the complete schematic symbol inventory",
            text_report(report),
        )

    def test_complete_report_cannot_omit_inventory_review_basis(self) -> None:
        with self.assertRaisesRegex(ValidationError, "inventory review basis"):
            ConnectorCoverageReport(status="COMPLETE", scope="Synthetic connector inventory")

    def test_interface_record_rejects_duplicate_pin_numbers(self) -> None:
        valid = interface_record()
        with self.assertRaisesRegex(ValueError, "pin numbers must be unique"):
            InterfaceRecord(
                id="duplicate",
                revision="synthetic-1",
                pins=(valid.pins[0], valid.pins[0]),
            )


if __name__ == "__main__":
    unittest.main()
