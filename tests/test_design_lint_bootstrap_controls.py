"""Synthetic controls for separating power bootstrap pins from boot straps."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import ComponentContract, DesignLintPolicy
from tests.design_lint_fixtures import coach, control_input_pins

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
]


def test_unconnected_bootstrap_pin_is_not_a_boot_mode_control() -> None:
    source = control_input_pins()
    bootstrap = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U1.3": "BOOTSTRAP"}}
    )

    report = evaluate("synthetic-bootstrap-pin", coach(bootstrap), DesignLintPolicy())

    assert not any(
        item.rule_id == "control.unconnected_control_input" and item.subject == "U1.3: BOOTSTRAP"
        for item in report.findings
    )


def test_bootstrap_capacitor_node_is_not_a_biased_control_input() -> None:
    source = control_input_pins(connected=True, visible_bias=False)
    components = {
        **source.components,
        "C1": ComponentContract(value="100nF", footprint="Device:C"),
    }
    pin_functions = {pin: "GPIO" for pin in source.pin_functions}
    pin_functions.update(
        {
            "U1.3": "BOOTSTRAP",
            "U1.4": "SW",
            "C1.1": "~",
            "C1.2": "~",
        }
    )
    pin_types = {
        **source.pin_electrical_types,
        "U1.4": "output",
        "C1.1": "passive",
        "C1.2": "passive",
    }
    bootstrap = source.model_copy(
        update={
            "components": components,
            "component_symbols": {**source.component_symbols, "C1": "Device:C"},
            "component_pin_numbers": {
                **source.component_pin_numbers,
                "C1": ("1", "2"),
            },
            "nets": {
                "BOOTSTRAP_NODE": ("U1.3", "C1.1"),
                "SW_NODE": ("U1.4", "C1.2"),
            },
            "pin_functions": pin_functions,
            "pin_electrical_types": pin_types,
        }
    )

    report = evaluate("synthetic-bootstrap-pin", coach(bootstrap), DesignLintPolicy())

    assert not any(
        item.rule_id == "control.connected_control_input_without_visible_bias"
        and item.evidence["net"] == ("BOOTSTRAP_NODE",)
        for item in report.findings
    )
