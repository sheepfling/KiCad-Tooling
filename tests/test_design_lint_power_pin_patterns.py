"""Focused synthetic regressions for the power pin patterns lint theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import (
    coach,
    cross_symbol_power,
    generic_connector_power_input_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.connector_lint,
]


class TestDesignLintPowerPinPatterns:
    def test_unconnected_supply_pin_across_symbols_is_reported(self) -> None:
        report = evaluate(
            "synthetic-ports",
            coach(cross_symbol_power(serial_connected=False)),
            DesignLintPolicy(),
        )
        assert len(report.findings) == 1
        assert report.findings[0].evidence["J2.1"] == ()

    def test_unconnected_supply_and_return_pins_without_a_peer_are_reported(self) -> None:
        isolated_named_pins = NetlistContract(
            components={},
            nets={"DATA": ("J1.2",)},
            component_symbols={"J1": "Synthetic:PowerPort"},
            pin_functions={"J1.1": "VCC", "J1.2": "TX", "J1.3": "GND"},
        )
        report = evaluate("synthetic-ports", coach(isolated_named_pins), DesignLintPolicy())
        assert report.status == "REVIEW"
        assert {item.rule_id for item in report.findings} == {
            "connector.unconnected_supply_pin",
            "connector.unconnected_return_pin",
        }
        assert {item.subject: item.evidence for item in report.findings} == {
            "J1.1: VCC": {"J1.1": ()},
            "J1.3: GND": {"J1.3": ()},
        }

        negative_rail = NetlistContract(
            components={},
            nets={},
            component_symbols={"J9": "Synthetic:NegativeSupplyPort"},
            pin_functions={"J9.1": "-5V"},
        )
        negative_report = evaluate("synthetic-ports", coach(negative_rail), DesignLintPolicy())
        assert len(negative_report.findings) == 1
        assert negative_report.findings[0].rule_id == "connector.unconnected_supply_pin"

        configured = evaluate(
            "synthetic-ports",
            coach(isolated_named_pins),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.unconnected_supply_pin",
                        mode="block",
                        reason="An unused port supply pin requires an owner decision",
                    ),
                    DesignLintRuleOverride(
                        rule_id="connector.unconnected_return_pin",
                        mode="off",
                        reason="This reviewed port does not use the return pin",
                    ),
                ),
            ),
        )
        assert configured.status == "FAIL"
        assert {item.rule_id: item.disposition for item in configured.findings} == {
            "connector.unconnected_supply_pin": "OPEN",
            "connector.unconnected_return_pin": "RULE_OFF",
        }

    def test_generic_power_input_report_includes_native_evidence(self) -> None:
        source = generic_connector_power_input_netlist(references=("J1",))
        report = evaluate("synthetic-generic-power-input", coach(source), DesignLintPolicy())
        assert report.status == "REVIEW"
        assert len(report.findings) == 1
        finding = report.findings[0]
        assert finding.rule_id == "connector.unconnected_power_input"
        assert finding.subject == "J1.1: generic native power-input pin is unassigned"
        assert finding.evidence == {
            "symbol": ("Synthetic:GenericPowerInputPort",),
            "pin_electrical_type": ("power_in",),
            "J1.1": (),
            "native_pin_function": ("1",),
        }
        assert "does not identify the contact's specific role" in finding.message

        blank_function_report = evaluate(
            "synthetic-blank-function-power-input",
            coach(generic_connector_power_input_netlist(function=None, references=("J1",))),
            DesignLintPolicy(),
        )
        assert {item.rule_id for item in blank_function_report.findings} == {
            "connector.unconnected_power_input"
        }
        assert "native_pin_function" not in blank_function_report.findings[0].evidence

        all_peers_open = evaluate(
            "synthetic-all-peer-power-inputs-open",
            coach(generic_connector_power_input_netlist()),
            DesignLintPolicy(),
        )
        assert {item.rule_id for item in all_peers_open.findings} == {
            "connector.unconnected_power_input"
        }
        assert {item.subject for item in all_peers_open.findings} == {
            "J1.1: generic native power-input pin is unassigned",
            "J2.1: generic native power-input pin is unassigned",
        }

    @pytest.mark.parametrize(
        "control",
        (
            pytest.param(
                generic_connector_power_input_netlist(connected=True, references=("J1",)),
                id="connected",
            ),
            pytest.param(
                generic_connector_power_input_netlist(function="VCC", references=("J1",)),
                id="named-supply",
            ),
            pytest.param(
                generic_connector_power_input_netlist(function="GND", references=("J1",)),
                id="named-return",
            ),
            pytest.param(
                generic_connector_power_input_netlist(
                    electrical_type="passive", references=("J1",)
                ),
                id="passive-pin",
            ),
            pytest.param(
                generic_connector_power_input_netlist(
                    electrical_type="power_out", references=("J1",)
                ),
                id="power-output-pin",
            ),
            pytest.param(
                generic_connector_power_input_netlist(dnp_references=("J1",), references=("J1",)),
                id="dnp-connector",
            ),
        ),
    )
    def test_generic_connector_power_input_valid_controls_are_suppressed(
        self, control: NetlistContract
    ) -> None:
        control_report = evaluate(
            "synthetic-generic-power-input-control",
            coach(control),
            DesignLintPolicy(),
        )
        assert "connector.unconnected_power_input" not in {
            item.rule_id for item in control_report.findings
        }

    def test_named_generic_connector_power_pins_keep_specific_rules(self) -> None:
        named_supply = evaluate(
            "synthetic-named-supply-stays-specific",
            coach(generic_connector_power_input_netlist(function="VCC", references=("J1",))),
            DesignLintPolicy(),
        )
        assert {item.rule_id for item in named_supply.findings} == {
            "connector.unconnected_supply_pin"
        }
        named_return = evaluate(
            "synthetic-named-return-stays-specific",
            coach(generic_connector_power_input_netlist(function="GND", references=("J1",))),
            DesignLintPolicy(),
        )
        assert {item.rule_id for item in named_return.findings} == {
            "connector.unconnected_return_pin"
        }

    def test_generic_connector_power_input_supports_policy_block_ignore_and_off(self) -> None:
        source = generic_connector_power_input_netlist(references=("J1",))
        initial = evaluate("synthetic-generic-power-input", coach(source), DesignLintPolicy())
        finding = next(
            item for item in initial.findings if item.rule_id == "connector.unconnected_power_input"
        )
        blocking = evaluate(
            "synthetic-generic-power-input",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.unconnected_power_input",
                        mode="block",
                        reason="Synthetic interface requires disposition of generic power pins",
                    ),
                )
            ),
        )
        assert blocking.status == "FAIL"
        ignored = evaluate(
            "synthetic-generic-power-input",
            coach(source),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id="connector.unconnected_power_input",
                        fingerprint=finding.fingerprint,
                        reason="Synthetic approved pinout leaves this connector contact open",
                    ),
                )
            ),
        )
        assert ignored.status == "PASS"
        assert ignored.findings[0].disposition == "IGNORED"
        disabled = evaluate(
            "synthetic-generic-power-input",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.unconnected_power_input",
                        mode="off",
                        reason="Synthetic port contact was reviewed as intentionally open",
                    ),
                )
            ),
        )
        assert disabled.findings[0].disposition == "RULE_OFF"

    def test_generic_power_input_type_is_order_stable(self) -> None:
        source = generic_connector_power_input_netlist()
        reordered = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            }
        )
        original_report = evaluate(
            "synthetic-generic-power-input", coach(source), DesignLintPolicy()
        )
        reordered_report = evaluate(
            "synthetic-generic-power-input", coach(reordered), DesignLintPolicy()
        )
        original_findings = tuple(
            (item.fingerprint, item.subject, item.evidence) for item in original_report.findings
        )
        assert (
            tuple(
                (item.fingerprint, item.subject, item.evidence)
                for item in reordered_report.findings
            )
            == original_findings
        )

    def test_connected_generic_power_input_clears_the_candidate(self) -> None:
        connected = generic_connector_power_input_netlist(connected=True)
        connected_report = evaluate(
            "synthetic-generic-power-input-control", coach(connected), DesignLintPolicy()
        )
        assert "connector.unconnected_power_input" not in {
            item.rule_id for item in connected_report.findings
        }

    def test_named_open_connector_supply_and_return_order_and_completion(self) -> None:
        source = NetlistContract(
            components={},
            nets={"DATA": ("J1.2",)},
            component_symbols={"J1": "Synthetic:PowerPort"},
            pin_functions={"J1.1": "VCC", "J1.2": "TX", "J1.3": "GND"},
        )
        reordered = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        original_report = evaluate("synthetic-ports", coach(source), DesignLintPolicy())
        reordered_report = evaluate("synthetic-ports", coach(reordered), DesignLintPolicy())
        target_rules = {"connector.unconnected_supply_pin", "connector.unconnected_return_pin"}
        original_findings = {
            item.rule_id: (item.fingerprint, item.evidence)
            for item in original_report.findings
            if item.rule_id in target_rules
        }
        reordered_findings = {
            item.rule_id: (item.fingerprint, item.evidence)
            for item in reordered_report.findings
            if item.rule_id in target_rules
        }
        assert set(original_findings) == target_rules
        assert reordered_findings == original_findings

        supply_connected = source.model_copy(update={"nets": {**source.nets, "+5V": ("J1.1",)}})
        supply_report = evaluate(
            "synthetic-ports-supply-connected", coach(supply_connected), DesignLintPolicy()
        )
        supply_rules = {item.rule_id for item in supply_report.findings}
        assert "connector.unconnected_supply_pin" not in supply_rules
        assert "connector.unconnected_return_pin" in supply_rules

        both_connected = supply_connected.model_copy(
            update={"nets": {**supply_connected.nets, "GND": ("J1.3",)}}
        )
        complete_report = evaluate(
            "synthetic-ports-complete", coach(both_connected), DesignLintPolicy()
        )
        complete_rules = {item.rule_id for item in complete_report.findings}
        assert not target_rules & complete_rules
