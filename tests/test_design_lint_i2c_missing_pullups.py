"""Focused synthetic regressions for the i2c lint theme."""

from __future__ import annotations

from typing import TypedDict

import pytest

from kicad_tooling.hwrepo.design_lint import (
    evaluate,
)
from kicad_tooling.hwrepo.models import (
    DesignLintFinding,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.resistor_paths import direct_resistors
from tests.design_lint_fixtures import (
    coach,
    i2c_netlist,
    i2c_netlist_with_series_sda,
    policy_without_i2c_map_prompt,
)
from tests.design_lint_fixtures.i2c_resistor_symbols import i2c_netlist_with_device_r_symbol

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


class I2cNetlistUpdates(TypedDict, total=False):
    """Netlist fields changed by the synthetic I2C symbol-boundary cases."""

    component_symbols: dict[str, str]
    dnp_components: tuple[str, ...]
    component_pin_numbers: dict[str, tuple[str, ...]]
    nets: dict[str, tuple[str, ...]]


def test_i2c_pullup_hint_detects_missing_or_invalid_local_resistors() -> None:
    policy = policy_without_i2c_map_prompt()
    report = evaluate("synthetic-i2c", coach(i2c_netlist()), policy)
    assert report.status == "REVIEW"
    open_findings = [item for item in report.findings if item.disposition == "OPEN"]
    assert len(open_findings) == 1
    finding = open_findings[0]
    assert finding.rule_id == "bus.i2c_missing_pullup"
    assert finding.evidence["missing_pullups"] == ("SDA", "SCL")
    assert "internal or off-board pull-ups" in finding.message
    one_line = evaluate("synthetic-i2c", coach(i2c_netlist(pullups=("SDA",))), policy)
    one_line_finding = next(item for item in one_line.findings if item.disposition == "OPEN")
    assert one_line_finding.evidence["missing_pullups"] == ("SCL",)
    connected = evaluate(
        "synthetic-i2c", coach(i2c_netlist(pullups=("SDA", "SCL"), resistance="4k7")), policy
    )
    assert connected.status == "PASS"
    assert not [item for item in connected.findings if item.disposition == "OPEN"]
    unpopulated_pullups = i2c_netlist(pullups=("SDA", "SCL")).model_copy(
        update={"dnp_components": ("R1", "R2")}
    )
    dnp_report = evaluate("synthetic-i2c", coach(unpopulated_pullups), policy)
    assert dnp_report.status == "REVIEW"
    dnp_finding = next(item for item in dnp_report.findings if item.disposition == "OPEN")
    assert dnp_finding.rule_id == "bus.i2c_missing_pullup"
    assert dnp_finding.evidence["missing_pullups"] == ("SDA", "SCL")
    invalid_value = evaluate(
        "synthetic-i2c", coach(i2c_netlist(pullups=("SDA", "SCL"), resistance="0R")), policy
    )
    assert invalid_value.status == "REVIEW"
    invalid_finding = next(item for item in invalid_value.findings if item.disposition == "OPEN")
    assert invalid_finding.evidence["missing_pullups"] == ("SDA", "SCL")
    negative_rail = evaluate(
        "synthetic-i2c", coach(i2c_netlist(pullups=("SDA", "SCL"), rail="-5V")), policy
    )
    assert negative_rail.status == "REVIEW"


@pytest.mark.design_lint_rule(rule_id="bus.i2c_missing_pullup")
@pytest.mark.parametrize(
    ("updates", "symbol"),
    (
        ({"component_symbols": {"X1": "Device:C"}}, "Device:C"),
        ({"component_symbols": {"X1": "Custom:Resistor"}}, "Custom:Resistor"),
        ({"dnp_components": ("X1",)}, "Device:R"),
        ({"component_pin_numbers": {}}, "Device:R"),
        (
            {
                "component_pin_numbers": {"X1": ("1", "2", "3")},
                "nets": {
                    "SDA_BUS": ("U1.1", "X1.1"),
                    "SCL_BUS": ("U1.2", "R2.1"),
                    "+3V3": ("R2.2", "X1.2"),
                    "AUX_UNCONNECTED_ROLE": ("X1.3",),
                },
            },
            "Device:R",
        ),
    ),
)
def test_i2c_missing_pullup_does_not_accept_unverified_symbol_resistors(
    updates: I2cNetlistUpdates,
    symbol: str,
) -> None:
    source = i2c_netlist_with_device_r_symbol(symbol=symbol).model_copy(update=updates)
    report = evaluate(
        "synthetic-i2c-symbol-boundary",
        coach(source),
        policy_without_i2c_map_prompt(),
    )

    assert "bus.i2c_missing_pullup" in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id="bus.i2c_missing_pullup")
def test_i2c_missing_pullup_recognizes_exact_device_r_symbol_and_is_order_stable() -> None:
    source = i2c_netlist_with_device_r_symbol()
    policy = policy_without_i2c_map_prompt()
    report = evaluate("synthetic-i2c-symbol-resistor", coach(source), policy)
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered_report = evaluate("synthetic-i2c-symbol-resistor", coach(reordered), policy)

    assert "bus.i2c_missing_pullup" not in {item.rule_id for item in report.findings}
    assert "bus.i2c_missing_pullup" not in {item.rule_id for item in reordered_report.findings}
    assert "X1" not in {item.reference for item in direct_resistors(source)}
    assert "X1" in {
        item.reference for item in direct_resistors(source, include_device_r_symbol=True)
    }


@pytest.mark.parametrize("resistance", ("1k", "100k"))
def test_i2c_pullup_resistance_boundary_is_a_valid_control(resistance: str) -> None:
    report = evaluate(
        "synthetic-i2c",
        coach(i2c_netlist(pullups=("SDA", "SCL"), resistance=resistance)),
        policy_without_i2c_map_prompt(),
    )
    assert report.status == "PASS"
    assert not [item for item in report.findings if item.disposition == "OPEN"]


def test_i2c_missing_pullup_is_order_stable_and_tracks_each_line_path() -> None:
    policy = policy_without_i2c_map_prompt()
    source = i2c_netlist()
    original = evaluate("synthetic-i2c", coach(source), policy)
    reordered_source = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    reordered = evaluate("synthetic-i2c", coach(reordered_source), policy)

    def finding_for(report: DesignLintReport) -> DesignLintFinding:
        return next(item for item in report.findings if item.rule_id == "bus.i2c_missing_pullup")

    original_finding = finding_for(original)
    reordered_finding = finding_for(reordered)
    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        original_finding.fingerprint,
        original_finding.evidence,
    )
    assert original_finding.evidence["missing_pullups"] == ("SDA", "SCL")
    complete = evaluate(
        "synthetic-i2c", coach(i2c_netlist(pullups=("SDA", "SCL"), resistance="4k7")), policy
    )
    assert "bus.i2c_missing_pullup" not in {item.rule_id for item in complete.findings}


@pytest.mark.parametrize(("connected_line", "remaining_line"), (("SDA", "SCL"), ("SCL", "SDA")))
def test_connecting_one_line_leaves_only_the_other_pullup_missing(
    connected_line: str,
    remaining_line: str,
) -> None:
    report = evaluate(
        "synthetic-i2c",
        coach(i2c_netlist(pullups=(connected_line,))),
        policy_without_i2c_map_prompt(),
    )
    finding = next(item for item in report.findings if item.rule_id == "bus.i2c_missing_pullup")
    assert finding.evidence["missing_pullups"] == (remaining_line,)


def test_i2c_series_pullup_paths_are_bounded_and_unbranched() -> None:
    policy = policy_without_i2c_map_prompt()
    series_control = evaluate("synthetic-i2c", coach(i2c_netlist_with_series_sda()), policy)
    assert series_control.status == "PASS"
    assert not [item for item in series_control.findings if item.disposition == "OPEN"]
    too_weak = evaluate("synthetic-i2c", coach(i2c_netlist_with_series_sda("56k", "56k")), policy)
    too_weak_findings = [item for item in too_weak.findings if item.disposition == "OPEN"]
    assert len(too_weak_findings) == 1
    assert too_weak_findings[0].rule_id == "bus.i2c_missing_pullup"
    assert too_weak_findings[0].evidence["missing_pullups"] == ("SDA",)
    branched = evaluate(
        "synthetic-i2c", coach(i2c_netlist_with_series_sda(branched_junction=True)), policy
    )
    branched_findings = [item for item in branched.findings if item.disposition == "OPEN"]
    assert len(branched_findings) == 1
    assert branched_findings[0].rule_id == "bus.i2c_missing_pullup"
    assert branched_findings[0].evidence["missing_pullups"] == ("SDA",)
    dnp = i2c_netlist_with_series_sda().model_copy(update={"dnp_components": ("R4",)})
    unpopulated = evaluate("synthetic-i2c", coach(dnp), policy)
    unpopulated_findings = [item for item in unpopulated.findings if item.disposition == "OPEN"]
    assert len(unpopulated_findings) == 1
    assert unpopulated_findings[0].evidence["missing_pullups"] == ("SDA",)


def test_i2c_pullup_hint_can_be_configured_per_project() -> None:
    report = evaluate(
        "synthetic-i2c",
        coach(i2c_netlist()),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.i2c_missing_pullup",
                    mode="block",
                    reason="Every local I2C bus requires reviewed pull-up evidence",
                ),
            )
        ),
    )
    assert report.status == "FAIL"
