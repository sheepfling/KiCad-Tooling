"""Architecture contract for the I2C SDA/SCL resistor bridge rule."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo import i2c_sda_scl_resistive_bridge, i2c_signal_endpoints
from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
    pytest.mark.rule_gate_integrity,
]


def test_resistor_bridge_rule_reuses_the_bounded_i2c_endpoint_owner() -> None:
    owner = (
        "kicad_tooling/hwrepo/i2c_sda_scl_resistive_bridge.py#"
        "i2c_sda_scl_resistive_bridge_candidates"
    )
    rule = next(
        item for item in rule_catalog().rules if item.rule_id == "bus.i2c_sda_scl_resistive_bridge"
    )

    assert line_count(HWREPO / "i2c_sda_scl_resistive_bridge.py") < IMPLEMENTATION_MAX_LINES
    assert line_count(HWREPO / "i2c_signal_endpoints.py") < IMPLEMENTATION_MAX_LINES
    assert rule.theme == "interfaces"
    assert rule.default_mode == "review"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
    assert i2c_sda_scl_resistive_bridge.i2c_signal_endpoints is (
        i2c_signal_endpoints.i2c_signal_endpoints
    )
