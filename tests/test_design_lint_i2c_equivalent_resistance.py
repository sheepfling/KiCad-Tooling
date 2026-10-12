"""Focused synthetic regressions for the i2c lint theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import (
    candidates,
    evaluate,
    fingerprint,
)
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.design_lint_fixtures import (
    coach,
    i2c_netlist_with_parallel_sda,
    i2c_netlist_with_series_sda,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


def test_i2c_parallel_pullups_are_reviewed_by_nominal_equivalent_resistance() -> None:
    low_resistance = evaluate(
        "synthetic-i2c", coach(i2c_netlist_with_parallel_sda()), DesignLintPolicy()
    )
    findings = [
        item
        for item in low_resistance.findings
        if item.rule_id == "bus.i2c_low_equivalent_resistance"
    ]
    assert len(findings) == 1
    assert findings[0].evidence["lines"] == ("SDA",)
    assert findings[0].evidence["equivalent_ohms"] == ("SDA=500Ω",)
    assert findings[0].evidence["pullup_resistors"] == ("R1=1000Ω to +3V3", "R3=1000Ω to +3V3")
    ordered = i2c_netlist_with_parallel_sda(parallel_resistance="1k5")
    reordered = ordered.model_copy(
        update={"components": dict(reversed(tuple(ordered.components.items())))}
    )
    first_candidate = next(
        item for item in candidates(ordered) if item.rule_id == "bus.i2c_low_equivalent_resistance"
    )
    reordered_candidate = next(
        item
        for item in candidates(reordered)
        if item.rule_id == "bus.i2c_low_equivalent_resistance"
    )
    assert fingerprint(first_candidate) == fingerprint(reordered_candidate)
    accepted = evaluate(
        "synthetic-i2c", coach(i2c_netlist_with_parallel_sda("4k7")), DesignLintPolicy()
    )
    assert not any(
        item.rule_id == "bus.i2c_low_equivalent_resistance" for item in accepted.findings
    )
    dnp_control = i2c_netlist_with_parallel_sda().model_copy(update={"dnp_components": ("R3",)})
    dnp_report = evaluate("synthetic-i2c", coach(dnp_control), DesignLintPolicy())
    assert not any(
        item.rule_id == "bus.i2c_low_equivalent_resistance" for item in dnp_report.findings
    )
    blocked = evaluate(
        "synthetic-i2c",
        coach(i2c_netlist_with_parallel_sda()),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.i2c_low_equivalent_resistance",
                    mode="block",
                    reason="The reviewed I2C bus requires at least 1 kΩ nominal pull-up resistance",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"


def test_i2c_low_equivalent_includes_series_pullup_paths() -> None:
    low_resistance = evaluate(
        "synthetic-i2c",
        coach(
            i2c_netlist_with_series_sda(
                "1k", "1k", base_pullups=("SDA", "SCL"), base_resistance="1k"
            )
        ),
        DesignLintPolicy(),
    )
    findings = [
        item
        for item in low_resistance.findings
        if item.rule_id == "bus.i2c_low_equivalent_resistance"
    ]
    assert len(findings) == 1
    assert findings[0].evidence["lines"] == ("SDA",)
    assert findings[0].evidence["equivalent_ohms"] == ("SDA=666.667Ω",)
    assert findings[0].evidence["pullup_resistors"] == ("R1=1000Ω to +3V3", "R3 + R4=2000Ω to +3V3")
    valid = evaluate(
        "synthetic-i2c",
        coach(
            i2c_netlist_with_series_sda(
                "4.7k", "4.7k", base_pullups=("SDA", "SCL"), base_resistance="4.7k"
            )
        ),
        DesignLintPolicy(),
    )
    assert not any(item.rule_id == "bus.i2c_low_equivalent_resistance" for item in valid.findings)
