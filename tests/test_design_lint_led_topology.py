"""Focused synthetic regressions for the led topology lint theme."""

from __future__ import annotations

import hashlib

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


def test_two_pin_led_directly_bridging_supply_and_return_is_configurable() -> None:
    source = led_rail_bridge_netlist()
    report = evaluate("synthetic-led-direct-rails", coach(source), DesignLintPolicy())
    findings = [
        item
        for item in report.findings
        if item.rule_id == "component.led_directly_across_supply_and_return"
    ]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == "D1: LED directly spans supply and return"
    assert finding.evidence["led_pins"] == ("D1.1", "D1.2")
    assert finding.evidence["positive_net"] == ("+3V3",)
    assert finding.evidence["return_net"] == ("GND",)
    assert "does not establish operating current" in finding.message
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
    assert blocked.status == "FAIL"
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
    assert ignored.status == "PASS"
    assert ignored.findings[0].disposition == "IGNORED"
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
    assert disabled.status == "PASS"
    assert disabled.findings[0].disposition == "RULE_OFF"


def test_led_bridge_is_order_stable_and_series_path_clears_it() -> None:
    rule_id = "component.led_directly_across_supply_and_return"
    source = led_rail_bridge_netlist()

    def lint(netlist: NetlistContract) -> tuple[str, DesignLintReport]:
        source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
        return (
            source_hash,
            evaluate("synthetic-led-direct-rails", coach(netlist, source_hash), DesignLintPolicy()),
        )

    source_hash, original = lint(source)
    assert original.netlist_sha256 == source_hash
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == rule_id
    }
    assert len(original_findings) == 1
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered_hash, reordered = lint(reordered_source)
    assert source_hash != reordered_hash
    assert reordered.netlist_sha256 == reordered_hash
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == rule_id
    }
    assert reordered_findings == original_findings
    repaired_hash, repaired = lint(led_rail_bridge_netlist(series_resistor=True))
    assert source_hash != repaired_hash
    assert rule_id not in {item.rule_id for item in repaired.findings}


def test_led_rail_bridge_predicate_uses_exact_topology_and_symbol_controls() -> None:
    parallel_resistor = led_rail_bridge_netlist(parallel_resistor=True)
    parallel_report = evaluate(
        "synthetic-led-parallel-resistor", coach(parallel_resistor), DesignLintPolicy()
    )
    assert "component.led_directly_across_supply_and_return" in {
        item.rule_id for item in parallel_report.findings
    }
    recognized_pin_functions = led_rail_bridge_netlist(
        positive_net="LOCAL_RAIL", pin_functions={"U1.1": "VDD", "U2.1": "GND"}
    ).model_copy(
        update={"nets": {"LOCAL_RAIL": ("D1.1", "U1.1"), "LOCAL_RETURN": ("D1.2", "U2.1")}}
    )
    recognized_report = evaluate(
        "synthetic-led-pin-function-rails", coach(recognized_pin_functions), DesignLintPolicy()
    )
    assert "component.led_directly_across_supply_and_return" in {
        item.rule_id for item in recognized_report.findings
    }


@pytest.mark.parametrize(
    "source",
    (
        pytest.param(led_rail_bridge_netlist(series_resistor=True), id="series-resistor"),
        pytest.param(led_rail_bridge_netlist(dnp=("D1",)), id="not-fitted"),
        pytest.param(led_rail_bridge_netlist(symbol="Custom:LED"), id="custom-symbol"),
        pytest.param(led_rail_bridge_netlist(pin_numbers=("1",)), id="incomplete-pin-map"),
        pytest.param(
            led_rail_bridge_netlist(positive_net="UNCLASSIFIED_SUPPLY"), id="unknown-rail"
        ),
        pytest.param(
            led_rail_bridge_netlist(
                positive_net="LOCAL_RAIL",
                pin_functions={"U1.1": "VDD", "U2.1": "GND"},
            ),
            id="power-function-rail",
        ),
    ),
)
def test_led_non_matching_topologies_remain_valid_controls(source: NetlistContract) -> None:
    report = evaluate("synthetic-led-rail-bridge-control", coach(source), DesignLintPolicy())
    assert "component.led_directly_across_supply_and_return" not in {
        item.rule_id for item in report.findings
    }
