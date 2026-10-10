"""Focused synthetic regressions for the led topology lint theme."""

from __future__ import annotations

import hashlib
import unittest

import pytest

from kicad_tooling.hwrepo.design_lint import (
    evaluate,
)
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import (
    coach,
    led_rail_bridge_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
]


class DesignLintLedTopologyTests(unittest.TestCase):
    def test_two_pin_led_directly_bridging_supply_and_return_is_configurable(self) -> None:
        source = led_rail_bridge_netlist()
        report = evaluate("synthetic-led-direct-rails", coach(source), DesignLintPolicy())
        findings = [
            item
            for item in report.findings
            if item.rule_id == "component.led_directly_across_supply_and_return"
        ]
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.subject, "D1: LED directly spans supply and return")
        self.assertEqual(finding.evidence["led_pins"], ("D1.1", "D1.2"))
        self.assertEqual(finding.evidence["positive_net"], ("+3V3",))
        self.assertEqual(finding.evidence["return_net"], ("GND",))
        self.assertIn("does not establish operating current", finding.message)

        blocked = evaluate(
            "synthetic-led-direct-rails",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="component.led_directly_across_supply_and_return",
                        mode="block",
                        reason="Synthetic project requires explicit review of direct rail bridges",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored = evaluate(
            "synthetic-led-direct-rails",
            coach(source),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic rail is independently current limited",
                    ),
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(ignored.findings[0].disposition, "IGNORED")

        disabled = evaluate(
            "synthetic-led-direct-rails",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="component.led_directly_across_supply_and_return",
                        mode="off",
                        reason="Synthetic project reviews this LED through a separate driver contract",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertEqual(disabled.findings[0].disposition, "RULE_OFF")

    def test_led_bridge_is_order_stable_and_series_path_clears_it(self) -> None:
        rule_id = "component.led_directly_across_supply_and_return"
        source = led_rail_bridge_netlist()

        def lint(netlist: NetlistContract) -> tuple[str, DesignLintReport]:
            source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
            return source_hash, evaluate(
                "synthetic-led-direct-rails",
                coach(netlist, source_hash),
                DesignLintPolicy(),
            )

        source_hash, original = lint(source)
        self.assertEqual(original.netlist_sha256, source_hash)
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(len(original_findings), 1)

        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered_hash, reordered = lint(reordered_source)
        self.assertNotEqual(source_hash, reordered_hash)
        self.assertEqual(reordered.netlist_sha256, reordered_hash)
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        repaired_hash, repaired = lint(led_rail_bridge_netlist(series_resistor=True))
        self.assertNotEqual(source_hash, repaired_hash)
        self.assertNotIn(rule_id, {item.rule_id for item in repaired.findings})

    def test_led_rail_bridge_predicate_uses_exact_topology_and_symbol_controls(self) -> None:
        controls = (
            led_rail_bridge_netlist(series_resistor=True),
            led_rail_bridge_netlist(dnp=("D1",)),
            led_rail_bridge_netlist(symbol="Custom:LED"),
            led_rail_bridge_netlist(pin_numbers=("1",)),
            led_rail_bridge_netlist(positive_net="UNCLASSIFIED_SUPPLY"),
            led_rail_bridge_netlist(
                positive_net="LOCAL_RAIL",
                pin_functions={"U1.1": "VDD", "U2.1": "GND"},
            ),
        )
        for source in controls:
            with self.subTest(
                nets=source.nets,
                dnp=source.dnp_components,
                symbols=source.component_symbols,
            ):
                report = evaluate(
                    "synthetic-led-rail-bridge-control", coach(source), DesignLintPolicy()
                )
                self.assertNotIn(
                    "component.led_directly_across_supply_and_return",
                    {item.rule_id for item in report.findings},
                )

        parallel_resistor = led_rail_bridge_netlist(parallel_resistor=True)
        parallel_report = evaluate(
            "synthetic-led-parallel-resistor", coach(parallel_resistor), DesignLintPolicy()
        )
        self.assertIn(
            "component.led_directly_across_supply_and_return",
            {item.rule_id for item in parallel_report.findings},
        )

        recognized_pin_functions = led_rail_bridge_netlist(
            positive_net="LOCAL_RAIL",
            pin_functions={"U1.1": "VDD", "U2.1": "GND"},
        ).model_copy(
            update={
                "nets": {
                    "LOCAL_RAIL": ("D1.1", "U1.1"),
                    "LOCAL_RETURN": ("D1.2", "U2.1"),
                }
            }
        )
        recognized_report = evaluate(
            "synthetic-led-pin-function-rails",
            coach(recognized_pin_functions),
            DesignLintPolicy(),
        )
        self.assertIn(
            "component.led_directly_across_supply_and_return",
            {item.rule_id for item in recognized_report.findings},
        )
