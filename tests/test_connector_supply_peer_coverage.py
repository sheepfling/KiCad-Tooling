"""Focused connector coverage checks for a single review theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage import evaluate
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ContractCoachReport,
    DesignLintPolicy,
    InterfacePin,
    InterfaceRecord,
    NetlistContract,
)
from tests.design_lint_fixtures.connector_coverage import (
    connector_supply_role_catalog,
    connector_supply_role_netlist,
    connector_supply_role_reviews,
    inventory_review,
    three_connector_supply_role_catalog,
    three_connector_supply_role_netlist,
    three_connector_supply_role_reviews,
)

pytestmark = [
    pytest.mark.connector_lint,
    pytest.mark.design_lint,
]


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
