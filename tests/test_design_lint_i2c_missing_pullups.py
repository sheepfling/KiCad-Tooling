"""Focused synthetic regressions for the i2c lint theme."""

from __future__ import annotations

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
from tests.design_lint_fixtures import (
    coach,
    i2c_netlist,
    i2c_netlist_with_series_sda,
    policy_without_i2c_map_prompt,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


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
