"""Connector review coverage remains distinct from inferred connectivity."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.connector_coverage import (
    evaluate,
)
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


def test_standard_connector_symbol_identity_finds_nonstandard_reference_candidates() -> None:
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

    assert (tuple(item.reference for item in coverage.entries)) == (("EXT1", "HDR1", "J1", "U7"))
    assert (coverage.status) == ("UNDECLARED")
    assert ("U8") not in ({item.reference for item in coverage.entries})
    assert ("U9") not in ({item.reference for item in coverage.entries})


def test_standard_test_point_library_control_does_not_create_connector_coverage() -> None:
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

    assert (coverage.status) == ("COMPLETE")
    assert (coverage.entries) == (())


def test_unreviewed_candidate_is_a_coverage_gap_and_keeps_lint_at_review() -> None:
    coverage = evaluate(observed_connector(), (), ())
    assert (coverage.status) == ("UNDECLARED")
    assert (coverage.entries[0].reference) == ("J1")
    assert (coverage.entries[0].status) == ("UNDECLARED")
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
    assert (report.status) == ("REVIEW")
    assert ("Connector coverage: UNDECLARED") in (text_report(report))
    assert ("UNDECLARED connector J1") in (text_report(report))


def test_complete_interface_review_accounts_for_every_catalog_and_symbol_pin() -> None:
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
    assert (coverage.status) == ("COMPLETE")
    assert (coverage.entries[0].status) == ("COVERED")
    assert (coverage.unbound_interface_ids) == (())
    assert (coverage.inventory_review_basis) == (
        "Synthetic review covered the complete schematic symbol inventory"
    )
    assert (coverage.entries[0].interface_pin_map) == ({"1": "1", "2": "2"})
    assert (coverage.entries[0].mapped_pins[0].interface_signal) == ("TX")
    assert (coverage.entries[0].mapped_pins[0].nets) == (("TX",))
    assert (coverage.entries[0].unlisted_pin_reasons) == (
        {"3": "Synthetic shield pin reviewed separately"}
    )


def test_reviewed_custom_symbol_discovers_exact_symbol_peers_for_coverage() -> None:
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

    assert ({item.reference: item.status for item in coverage.entries}) == (
        {"A1": "COVERED", "A2": "UNDECLARED"}
    )
    assert (coverage.status) == ("UNDECLARED")

    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
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
    assert (reordered_coverage) == (coverage)

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
    assert (dispositioned.status) == ("COMPLETE")
    assert ({item.reference: item.status for item in dispositioned.entries}) == (
        {"A1": "COVERED", "A2": "NOT_APPLICABLE"}
    )


def test_reviewed_supply_domains_compare_generic_contacts_across_symbols() -> None:
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
    assert ("connector.repeated_pin_function") not in (
        {finding.rule_id for finding in baseline.findings}
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
    assert (coverage.status) == ("COMPLETE")
    mapped_supply = next(pin for entry in coverage.entries for pin in entry.mapped_pins)
    assert (mapped_supply.voltage_domain) == ("external-5v")

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
    assert (fault.status) == ("REVIEW")
    assert ({finding.rule_id for finding in fault.findings}) == (
        {"connector.repeated_pin_function"}
    )
    finding = fault.findings[0]
    assert (dict(finding.evidence)) == (
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
        }
    )
    assert ("does not require commonality") in (finding.message)

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
    assert (open_supply_coverage.status) == ("COMPLETE")
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
    assert (open_supply_report.status) == ("REVIEW")
    assert ({item.rule_id for item in open_supply_report.findings}) == (
        {"connector.repeated_pin_function"}
    ), "the cross-symbol role finding reports the open contact without a duplicate prompt"
    open_supply_finding = open_supply_report.findings[0]
    assert (open_supply_finding.evidence["J1.2"]) == (("NODE_ALPHA",))
    assert (open_supply_finding.evidence["J2.5"]) == (())
    assert ("does not require commonality") in (open_supply_finding.message)

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
    assert (fault.netlist_sha256) != (reordered_fault.netlist_sha256)
    assert (reordered_fault.status) == (fault.status)
    assert (
        tuple(
            (item.rule_id, item.subject, item.message, item.evidence, item.fingerprint)
            for item in reordered_fault.findings
        )
    ) == (
        tuple(
            (item.rule_id, item.subject, item.message, item.evidence, item.fingerprint)
            for item in fault.findings
        )
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
    assert (common_report.status) == ("PASS")
    assert not (common_report.findings)

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
    assert (separate_domains.status) == ("PASS")
    assert not (separate_domains.findings)


def test_three_mapped_supply_peers_localize_one_split_from_two_common() -> None:
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
    assert (split_coverage.status) == ("COMPLETE")
    assert all(entry.status == "COVERED" for entry in split_coverage.entries)
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
    assert ("connector.repeated_pin_function") not in (
        {finding.rule_id for finding in baseline.findings}
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
    assert (fault.status) == ("REVIEW")
    assert (len(fault.findings)) == (1)
    finding = fault.findings[0]
    assert (finding.rule_id) == ("connector.repeated_pin_function")
    assert ({key: finding.evidence[key] for key in ("J1.2", "J2.5", "J3.9")}) == (
        {
            "J1.2": ("SUPPLY_A",),
            "J2.5": ("SUPPLY_A",),
            "J3.9": ("SUPPLY_B",),
        }
    )
    assert (finding.evidence["reviewed_voltage_domain"]) == (("external-5v",))
    assert ("does not require commonality") in (finding.message)

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
    assert (common_report.status) == ("PASS")
    assert not (common_report.findings)

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
    assert (independent_domain_report.status) == ("PASS")
    assert not (independent_domain_report.findings)


def test_mapped_generic_peer_roles_suppress_duplicate_pin_divergence() -> None:
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

    assert ({finding.rule_id for finding in report.findings}) == (
        {"connector.repeated_pin_function"}
    )
    assert (report.findings[0].evidence["J1.1"]) == (("SUPPLY_A",))
    assert (report.findings[0].evidence["J2.1"]) == (("SUPPLY_B",))

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
    assert (partial_coverage.status) == ("UNDECLARED")
    assert (
        next(entry.status for entry in partial_coverage.entries if entry.reference == "J3")
    ) == ("UNDECLARED")
    assert ("connector.repeated_pin_function") in (
        {finding.rule_id for finding in partial_report.findings}
    )
    assert (generic_finding.evidence["outlier_pins"]) == (("J2.1",))
    assert (generic_finding.evidence["J3.1"]) == (("SUPPLY_A",))


def test_reviewed_return_roles_refine_connector_net_heuristics() -> None:
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
    assert (split_coverage.status) == ("COMPLETE")
    assert (
        next(entry for entry in split_coverage.entries if entry.reference == "J2")
        .mapped_pins[2]
        .role
    ) == ("return")

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
    assert (split_report.status) == ("REVIEW")
    return_finding = next(
        finding
        for finding in split_report.findings
        if finding.rule_id == "connector.repeated_pin_function"
    )
    assert (dict(return_finding.evidence)) == (
        {
            "J1.3": ("USB_RETURN",),
            "J2.3": ("SERIAL_RETURN",),
            "role_classification_sources": (
                "J1.3: project interface catalog role=return; native symbol function=GND",
                "J2.3: project interface catalog role=return; native symbol function=Pin_3",
            ),
        }
    )
    assert ("role classification alone does not require commonality") in (return_finding.message)
    rendered_split = text_report(split_report)
    assert (f"Interface catalog: catalog/interfaces.json ({'b' * 64})") in (rendered_split)
    assert (
        "role_classification_sources: J1.3: project interface catalog role=return; "
        "native symbol function=GND, "
        "J2.3: project interface catalog role=return; native symbol function=Pin_3"
    ) in (rendered_split)
    assert ("Interface pin 3 (RETURN) maps to J2.3: role=return") in (rendered_split)
    assert ("connector.no_connected_return") not in (
        {finding.rule_id for finding in split_report.findings}
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
                "unlisted_pin_reasons": dict(reversed(tuple(review.unlisted_pin_reasons.items()))),
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
    assert (reordered_coverage) == (split_coverage)
    assert (reordered_report) == (split_report)

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
    assert (disabled_report.status) == ("PASS")
    assert (len(disabled_report.findings)) == (1)
    assert (disabled_report.findings[0].mode) == ("off")
    assert (disabled_report.findings[0].disposition) == ("RULE_OFF")

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
    assert ("connector.no_connected_return") in (
        {finding.rule_id for finding in unbound_catalog_report.findings}
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
    assert ("connector.no_connected_return") in (
        {finding.rule_id for finding in incomplete_map_report.findings}
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
    assert (common_report.status) == ("PASS")
    assert not (common_report.findings)

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
    assert (open_return_report.status) == ("REVIEW")
    return_pin_finding = next(
        finding
        for finding in open_return_report.findings
        if finding.rule_id == "connector.repeated_pin_function"
    )
    assert (return_pin_finding.evidence["J2.3"]) == (())
    assert ("connector.no_connected_return") not in (
        {finding.rule_id for finding in open_return_report.findings}
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
    assert (supply_pin_finding.subject) == ("J2.4: V+")
    assert (supply_pin_finding.evidence["role_source"]) == (("project interface catalog",))

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
    assert ("connector.no_connected_return") in (
        {finding.rule_id for finding in stale_report.findings}
    )


def test_missing_and_unknown_catalog_or_symbol_pins_are_named() -> None:
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
    assert (coverage.status) == ("INCOMPLETE")
    assert (entry.status) == ("INCOMPLETE")
    assert (entry.interface_pins_unmapped) == (("2",))
    assert (entry.interface_pins_unknown) == (("stale",))
    assert (entry.component_pins_unaccounted) == (("2", "3"))
    assert (entry.component_pins_unknown) == (("9",))


def test_explicit_not_applicable_decision_covers_a_candidate_without_joining_nets() -> None:
    review = ConnectorInterfaceReview(
        reference="J1",
        disposition="not_applicable",
        basis="Synthetic connector is a local service jumper, not an external interface",
    )
    coverage = evaluate(observed_connector(), (), (review,), inventory_review=inventory_review())
    assert (coverage.status) == ("COMPLETE")
    assert (coverage.entries[0].status) == ("NOT_APPLICABLE")


def test_reviewed_connector_rows_still_need_complete_inventory_scope() -> None:
    review = ConnectorInterfaceReview(
        reference="J1",
        disposition="not_applicable",
        basis="Synthetic connector is a local service jumper",
    )
    coverage = evaluate(observed_connector(), (), (review,))
    assert (coverage.status) == ("SCOPE_UNREVIEWED")


def test_explicit_review_can_cover_a_reference_outside_candidate_prefixes() -> None:
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
    assert (coverage.status) == ("COMPLETE")
    assert (coverage.entries[0].status) == ("NOT_APPLICABLE")


def test_stale_review_and_missing_interface_record_are_incomplete() -> None:
    stale = ConnectorInterfaceReview(
        reference="J2",
        disposition="not_applicable",
        basis="Synthetic old reference",
    )
    stale_coverage = evaluate(observed_connector(), (), (stale,))
    assert (stale_coverage.status) == ("INCOMPLETE")
    stale_entry = next(entry for entry in stale_coverage.entries if entry.reference == "J2")
    assert (stale_entry.status) == ("STALE")

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
    assert (missing.status) == ("INCOMPLETE")
    assert ("missing-interface") in (missing.entries[0].issues[0])


def test_no_candidates_without_declarations_is_explicitly_unassessed() -> None:
    observed = observed_connector(candidate=False)
    coverage = evaluate(observed, (), ())
    assert (coverage.status) == ("UNASSESSED")
    assert ("does not prove") in (coverage.scope)
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
    assert (report.status) == ("REVIEW")
    assert ("connector_inventory_review") in (" ".join(report.next_actions))


def test_explicit_inventory_review_can_confirm_no_external_connectors() -> None:
    observed = NetlistContract(components={}, nets={})
    coverage = evaluate(observed, (), (), inventory_review=inventory_review())
    assert (coverage.status) == ("COMPLETE")
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
    assert (report.status) == ("PASS")
    assert (
        "Inventory review basis: Synthetic review covered the complete schematic symbol inventory"
    ) in (text_report(report))


def test_complete_report_cannot_omit_inventory_review_basis() -> None:
    with pytest.raises(ValidationError, match="inventory review basis"):
        ConnectorCoverageReport(status="COMPLETE", scope="Synthetic connector inventory")


def test_interface_record_rejects_duplicate_pin_numbers() -> None:
    valid = interface_record()
    with pytest.raises(ValueError, match="pin numbers must be unique"):
        InterfaceRecord(
            id="duplicate",
            revision="synthetic-1",
            pins=(valid.pins[0], valid.pins[0]),
        )
