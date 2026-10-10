"""Focused synthetic regressions for the connector roles lint theme."""

from __future__ import annotations

import unittest

import pytest

from kicad_tooling.hwrepo.design_lint import (
    candidates,
    evaluate,
    fingerprint,
)
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    DesignLintIgnore,
    DesignLintPolicy,
    NetlistContract,
)
from tests.design_lint_fixtures import (
    coach,
    cross_symbol_power,
    cross_symbol_returns,
    custom_reviewed_connector_peers,
    multiconductor_connector,
    observed,
    standard_connector_identity_peers,
    three_port_power_pin_drift,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
    pytest.mark.return_path_lint,
]


class DesignLintConnectorRoleTests(unittest.TestCase):
    def test_connector_population_heuristics_ignore_dnp_instances(self) -> None:
        peers = NetlistContract(
            components={},
            nets={
                "USB_RETURN": ("J1.1",),
                "SERIAL_RETURN": ("J2.1",),
                "DATA_A": ("J2.3",),
                "DATA_B": ("J2.4",),
                "DATA_C": ("J2.5",),
            },
            component_symbols={"J1": "Synthetic:Port", "J2": "Synthetic:Port"},
            pin_functions={
                "J1.1": "GND",
                "J2.1": "GND",
                "J2.2": "VBUS",
                "J2.3": "1",
                "J2.4": "2",
                "J2.5": "3",
            },
        )
        populated = evaluate("synthetic-populated-ports", coach(peers), DesignLintPolicy())
        self.assertEqual(
            {item.rule_id for item in populated.findings},
            {"connector.repeated_pin_function", "connector.unconnected_supply_pin"},
        )

        dnp_peers = peers.model_copy(update={"dnp_components": ("j2",)})
        dnp = evaluate("synthetic-dnp-ports", coach(dnp_peers), DesignLintPolicy())
        self.assertFalse(dnp.findings)

        open_named_pins = NetlistContract(
            components={},
            nets={"DATA": ("J3.1",)},
            dnp_components=("J3",),
            component_symbols={"J3": "Synthetic:Port"},
            pin_functions={"J3.1": "DATA", "J3.2": "VBUS", "J3.3": "GND"},
        )
        open_pin_report = evaluate(
            "synthetic-dnp-open-pins", coach(open_named_pins), DesignLintPolicy()
        )
        self.assertFalse(open_pin_report.findings)

        no_return = multiconductor_connector(return_named=False)
        fitted_no_return = evaluate(
            "synthetic-fitted-no-return", coach(no_return), DesignLintPolicy()
        )
        self.assertIn(
            "connector.no_connected_return",
            {item.rule_id for item in fitted_no_return.findings},
        )
        dnp_no_return = evaluate(
            "synthetic-dnp-no-return",
            coach(no_return.model_copy(update={"dnp_components": ("J1",)})),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "connector.no_connected_return",
            {item.rule_id for item in dnp_no_return.findings},
        )

    def test_connector_identity_uses_standard_symbols_and_project_reviewed_custom_refs(
        self,
    ) -> None:
        fault = evaluate(
            "synthetic-standard-connector-identities",
            coach(standard_connector_identity_peers()),
            DesignLintPolicy(),
        )
        fault_rules = {item.rule_id for item in fault.findings}
        self.assertIn("connector.repeated_pin_function", fault_rules)
        self.assertNotIn("component.unconnected_supply_pin", fault_rules)
        self.assertNotIn("power.ic_rail_without_fitted_capacitor", fault_rules)
        repeated = next(
            item for item in fault.findings if item.rule_id == "connector.repeated_pin_function"
        )
        self.assertIn("U7.2", repeated.evidence)

        control = evaluate(
            "synthetic-standard-connector-control",
            coach(standard_connector_identity_peers(common_return=True, supply_connected=True)),
            DesignLintPolicy(),
        )
        self.assertFalse(control.findings)

        dnp = evaluate(
            "synthetic-standard-connector-dnp-control",
            coach(standard_connector_identity_peers(dnp=("U7",))),
            DesignLintPolicy(),
        )
        self.assertFalse(dnp.findings)

        generic_peer_fault = NetlistContract(
            components={
                reference: ComponentContract(value="Synthetic connector", footprint="")
                for reference in ("J1", "U7", "J2")
            },
            nets={
                "GND": ("J1.1", "U7.1", "J2.1"),
                "DATA": ("J1.2", "J2.2"),
            },
            component_symbols={
                reference: "Connector_Generic:Conn_01x02" for reference in ("J1", "U7", "J2")
            },
            component_pin_numbers={reference: ("1", "2") for reference in ("J1", "U7", "J2")},
            pin_functions={f"{reference}.1": "GND" for reference in ("J1", "U7", "J2")},
        )
        peer_fault = evaluate(
            "synthetic-standard-connector-peer-outlier",
            coach(generic_peer_fault),
            DesignLintPolicy(),
        )
        peer_finding = next(
            item
            for item in peer_fault.findings
            if item.rule_id == "connector.peer_pin_assignment_outlier"
        )
        self.assertIn("U7.2", peer_finding.evidence)
        peer_control = evaluate(
            "synthetic-standard-connector-peer-control",
            coach(
                generic_peer_fault.model_copy(
                    update={
                        "nets": {"GND": ("J1.1", "U7.1", "J2.1"), "DATA": ("J1.2", "U7.2", "J2.2")}
                    }
                )
            ),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "connector.peer_pin_assignment_outlier",
            {item.rule_id for item in peer_control.findings},
        )

        custom = custom_reviewed_connector_peers()
        unreviewed = evaluate(
            "synthetic-custom-connector-unreviewed",
            coach(custom),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "connector.repeated_pin_function",
            {item.rule_id for item in unreviewed.findings},
        )
        coverage = ConnectorCoverageReport(
            status="COMPLETE",
            scope="Synthetic project-reviewed interface references",
            inventory_review_basis="The synthetic interface inventory is complete",
            entries=(
                ConnectorCoverageEntry(
                    reference="A1",
                    status="COVERED",
                    interface_id="synthetic_port",
                    basis="The symbol was reviewed as an external connector",
                ),
                ConnectorCoverageEntry(
                    reference="A2",
                    status="COVERED",
                    interface_id="synthetic_port",
                    basis="The symbol was reviewed as an external connector",
                ),
            ),
        )
        reviewed = evaluate(
            "synthetic-custom-connector-reviewed",
            coach(custom),
            DesignLintPolicy(),
            connector_coverage=coverage,
        )
        self.assertIn(
            "connector.repeated_pin_function",
            {item.rule_id for item in reviewed.findings},
        )

        def return_coverage_netlist(*, connected_return: bool) -> NetlistContract:
            nets = {
                "DATA_A": ("U8.1",),
                "DATA_B": ("U8.2",),
                "DATA_C": ("U8.3",),
            }
            pin_functions = {f"U8.{number}": str(number) for number in (1, 2, 3)}
            pin_numbers = ("1", "2", "3")
            if connected_return:
                nets["GND"] = ("U8.4",)
                pin_functions["U8.4"] = "GND"
                pin_numbers = (*pin_numbers, "4")
            return NetlistContract(
                components={"U8": ComponentContract(value="Synthetic port", footprint="")},
                nets=nets,
                component_symbols={"U8": "Connector_Generic:Conn_01x04"},
                component_pin_numbers={"U8": pin_numbers},
                pin_functions=pin_functions,
            )

        no_return = evaluate(
            "synthetic-standard-connector-no-return",
            coach(return_coverage_netlist(connected_return=False)),
            DesignLintPolicy(),
        )
        self.assertIn(
            "connector.no_connected_return",
            {item.rule_id for item in no_return.findings},
        )
        with_return = evaluate(
            "synthetic-standard-connector-return-control",
            coach(return_coverage_netlist(connected_return=True)),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "connector.no_connected_return",
            {item.rule_id for item in with_return.findings},
        )

    def test_exact_ignore_resurfaces_after_connection_changes(self) -> None:
        initial = evaluate("synthetic-ports", coach(observed()), DesignLintPolicy())
        power = next(item for item in initial.findings if item.subject.endswith("PWR"))
        policy = DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id="connector.repeated_pin_function",
                    fingerprint=power.fingerprint,
                    reason="Independent review permits the currently unconnected third port",
                ),
            ),
        )
        ignored = evaluate("synthetic-ports", coach(observed()), policy)
        self.assertEqual(
            next(item for item in ignored.findings if item.subject.endswith("PWR")).disposition,
            "IGNORED",
        )
        changed = evaluate("synthetic-ports", coach(observed(True)), policy)
        self.assertEqual(changed.status, "REVIEW")
        self.assertEqual(changed.stale_ignores, policy.ignores)
        self.assertNotEqual(
            fingerprint(
                next(item for item in candidates(observed()) if item.subject.endswith("PWR"))
            ),
            fingerprint(
                next(item for item in candidates(observed(True)) if item.subject.endswith("PWR"))
            ),
        )

    def test_return_functions_across_connector_symbols_need_review(self) -> None:
        report = evaluate("synthetic-ports", coach(cross_symbol_returns()), DesignLintPolicy())
        self.assertEqual(report.status, "REVIEW")
        returns = [
            item
            for item in report.findings
            if item.subject == "multiple connector symbols: ground/return"
        ]
        self.assertEqual(len(returns), 1)
        self.assertEqual(
            returns[0].evidence,
            {"J1.4": ("USB_RETURN",), "J2.7": ("SERIAL_RETURN",)},
        )
        self.assertIn("common, bonded, or intentionally isolated", returns[0].message)

    def test_cross_connector_return_order_preserves_finding_and_commoning_clears_it(self) -> None:
        separate = cross_symbol_returns()
        reordered = separate.model_copy(
            update={
                "nets": dict(reversed(tuple(separate.nets.items()))),
                "component_symbols": dict(reversed(tuple(separate.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(separate.pin_functions.items()))),
            }
        )
        original_report = evaluate("synthetic-ports", coach(separate), DesignLintPolicy())
        reordered_report = evaluate("synthetic-ports", coach(reordered), DesignLintPolicy())
        original_finding = next(
            item
            for item in original_report.findings
            if item.subject == "multiple connector symbols: ground/return"
        )
        reordered_finding = next(
            item
            for item in reordered_report.findings
            if item.subject == "multiple connector symbols: ground/return"
        )
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )

        common_report = evaluate(
            "synthetic-ports-common",
            coach(cross_symbol_returns(common=True)),
            DesignLintPolicy(),
        )
        self.assertEqual(common_report.status, "PASS")
        self.assertNotIn(
            "connector.repeated_pin_function",
            {item.rule_id for item in common_report.findings},
        )

    def test_unconnected_return_pin_across_symbols_is_reported(self) -> None:
        report = evaluate(
            "synthetic-ports",
            coach(cross_symbol_returns(serial_connected=False)),
            DesignLintPolicy(),
        )
        returns = [
            item
            for item in report.findings
            if item.subject == "multiple connector symbols: ground/return"
        ]
        self.assertEqual(len(returns), 1)
        self.assertEqual(returns[0].evidence["J2.7"], ())

    def test_supply_pins_across_connector_symbols_need_review(self) -> None:
        report = evaluate("synthetic-ports", coach(cross_symbol_power()), DesignLintPolicy())
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(report.findings), 1)
        finding = report.findings[0]
        self.assertEqual(finding.subject, "multiple connector symbols: PWR")
        self.assertEqual(
            finding.evidence,
            {"J1.1": ("USB_SUPPLY",), "J2.1": ("SERIAL_SUPPLY",)},
        )
        self.assertIn("independent supplies", finding.message)

    def test_three_generic_power_pins_report_different_and_missing_sibling_assignments(
        self,
    ) -> None:
        report = evaluate(
            "synthetic-three-port-power",
            coach(three_port_power_pin_drift()),
            DesignLintPolicy(),
        )
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(
            {item.rule_id for item in report.findings},
            {"connector.repeated_pin_function", "net.numbered_power_rails"},
        )

        sibling_pins = next(
            item for item in report.findings if item.rule_id == "connector.repeated_pin_function"
        )
        self.assertEqual(
            sibling_pins.evidence,
            {"J1.1": ("+5V_1",), "J2.1": ("5V-2",), "J3.1": ()},
        )
        numbered_rails = next(
            item for item in report.findings if item.rule_id == "net.numbered_power_rails"
        )
        self.assertEqual(numbered_rails.evidence, {"+5V_1": ("J1.1",), "5V-2": ("J2.1",)})

        common = evaluate(
            "synthetic-three-port-power-common",
            coach(three_port_power_pin_drift(common=True)),
            DesignLintPolicy(),
        )
        self.assertEqual(common.status, "PASS")
        self.assertFalse(common.findings)

    def test_numbered_power_rail_order_is_stable_and_commoning_clears_the_hint(self) -> None:
        source = three_port_power_pin_drift()
        reordered = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        original_report = evaluate("synthetic-three-port-power", coach(source), DesignLintPolicy())
        reordered_report = evaluate(
            "synthetic-three-port-power", coach(reordered), DesignLintPolicy()
        )
        original_finding = next(
            item for item in original_report.findings if item.rule_id == "net.numbered_power_rails"
        )
        reordered_finding = next(
            item for item in reordered_report.findings if item.rule_id == "net.numbered_power_rails"
        )
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )

        common_report = evaluate(
            "synthetic-three-port-power-common",
            coach(three_port_power_pin_drift(common=True)),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "net.numbered_power_rails", {item.rule_id for item in common_report.findings}
        )
