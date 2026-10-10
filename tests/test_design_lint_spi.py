"""Focused synthetic regressions for the spi lint theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import (
    evaluate,
)
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import (
    coach,
    spi_active_low_select_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


def test_spi_active_low_select_bias_hint_is_review_only_and_configurable() -> None:
    report = evaluate(
        "synthetic-spi-bias",
        coach(spi_active_low_select_netlist()),
        DesignLintPolicy(),
    )
    assert (report.status) == ("REVIEW")
    assert (len(report.findings)) == (1)
    finding = report.findings[0]
    assert (finding.rule_id) == ("bus.spi_active_low_chip_select_without_pullup")
    assert (finding.mode) == ("review")
    assert (finding.evidence) == (
        {
            "net": ("SPI_CS_N",),
            "active_low_chip_select_pins": ("U2.1",),
            "recognized_positive_rails": ("+3V3",),
            "visible_pullup_paths": (),
        }
    )
    assert ("internal or off-board bias") in (finding.message)

    blocked = evaluate(
        "synthetic-spi-bias",
        coach(spi_active_low_select_netlist()),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.spi_active_low_chip_select_without_pullup",
                    mode="block",
                    reason="This project's reviewed SPI devices require an external idle bias",
                ),
            )
        ),
    )
    assert (blocked.status) == ("FAIL")

    disabled = evaluate(
        "synthetic-spi-bias",
        coach(spi_active_low_select_netlist()),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.spi_active_low_chip_select_without_pullup",
                    mode="off",
                    reason="This interface's controller guarantees the inactive state",
                ),
            )
        ),
    )
    assert (disabled.status) == ("PASS")
    assert (disabled.findings[0].disposition) == ("RULE_OFF")

    ignored = evaluate(
        "synthetic-spi-bias",
        coach(spi_active_low_select_netlist()),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="Reviewed internal reset bias for this synthetic peripheral",
                ),
            )
        ),
    )
    assert (ignored.status) == ("PASS")
    assert (ignored.findings[0].disposition) == ("IGNORED")


@pytest.mark.parametrize(
    "values",
    (
        pytest.param(("10k",), id="single-pullup"),
        pytest.param(("4.7k", "4.7k"), id="split-pullups"),
    ),
)
def test_spi_select_bias_recognizes_pullup_paths(values: tuple[str, ...]) -> None:
    report = evaluate(
        "synthetic-spi-bias",
        coach(spi_active_low_select_netlist(resistor_values=values)),
        DesignLintPolicy(),
    )

    assert all(
        item.rule_id != "bus.spi_active_low_chip_select_without_pullup" for item in report.findings
    )


@pytest.mark.parametrize(
    "control",
    (
        pytest.param(spi_active_low_select_netlist(device_dnp=True), id="dnp-device"),
        pytest.param(spi_active_low_select_netlist(select_function="CS"), id="not-active-low"),
        pytest.param(
            spi_active_low_select_netlist(select_electrical_type="output"),
            id="output-pin",
        ),
    ),
)
def test_spi_select_bias_ignores_valid_controls(control: NetlistContract) -> None:
    report = evaluate("synthetic-spi-bias", coach(control), DesignLintPolicy())

    assert all(
        item.rule_id != "bus.spi_active_low_chip_select_without_pullup" for item in report.findings
    )


@pytest.mark.parametrize(
    "fault",
    (
        pytest.param(
            spi_active_low_select_netlist(resistor_values=("10k",), resistor_dnp=("R1",)),
            id="dnp-pullup",
        ),
        pytest.param(spi_active_low_select_netlist(resistor_values=("0R",)), id="zero-ohm"),
        pytest.param(
            spi_active_low_select_netlist(resistor_values=("220k",)),
            id="out-of-range",
        ),
        pytest.param(
            spi_active_low_select_netlist(resistor_values=("10k",), resistor_rail="GND"),
            id="wrong-rail",
        ),
    ),
)
def test_spi_select_bias_reports_unusable_pullup_paths(fault: NetlistContract) -> None:
    report = evaluate("synthetic-spi-bias", coach(fault), DesignLintPolicy())

    assert any(
        item.rule_id == "bus.spi_active_low_chip_select_without_pullup" for item in report.findings
    )


def test_spi_select_bias_finding_is_order_stable_and_fitted_path_clears_it() -> None:
    def with_gpio_control(resistor_values: tuple[str, ...] = ()) -> NetlistContract:
        base = spi_active_low_select_netlist(resistor_values=resistor_values)
        return base.model_copy(
            update={
                "nets": {**base.nets, "CONTROL_GPIO": ("U1.4",)},
                "pin_functions": {**base.pin_functions, "U1.4": "GPIO"},
                "pin_electrical_types": {**base.pin_electrical_types, "U1.4": "input"},
                "component_pin_numbers": {
                    **base.component_pin_numbers,
                    "U1": (*base.component_pin_numbers["U1"], "4"),
                },
            }
        )

    source = with_gpio_control()
    original = evaluate("synthetic-spi-bias", coach(source), DesignLintPolicy())
    rule_id = "bus.spi_active_low_chip_select_without_pullup"
    original_finding = next(item for item in original.findings if item.rule_id == rule_id)
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered = evaluate("synthetic-spi-bias", coach(reordered_source), DesignLintPolicy())
    reordered_finding = next(item for item in reordered.findings if item.rule_id == rule_id)
    assert ((reordered_finding.fingerprint, reordered_finding.evidence)) == (
        (original_finding.fingerprint, original_finding.evidence)
    )

    repaired = evaluate(
        "synthetic-spi-bias",
        coach(with_gpio_control(("10k",))),
        DesignLintPolicy(),
    )
    assert (rule_id) not in ({item.rule_id for item in repaired.findings})
