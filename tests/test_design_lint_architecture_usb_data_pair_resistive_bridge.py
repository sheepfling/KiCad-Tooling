"""Architecture contract for the USB data-pair resistor review rule."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo import usb_data_pair_endpoints, usb_data_pair_resistive_bridge
from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
    pytest.mark.rule_gate_integrity,
]


def test_resistive_bridge_rule_reuses_bounded_pair_inventory() -> None:
    owner = (
        "kicad_tooling/hwrepo/usb_data_pair_resistive_bridge.py#"
        "usb_data_pair_resistive_bridge_candidates"
    )
    rule = next(
        item for item in rule_catalog().rules if item.rule_id == "bus.usb_dp_dm_resistive_bridge"
    )
    modules = (
        HWREPO / "usb_data_pair_endpoints.py",
        HWREPO / "usb_data_pair_resistive_bridge.py",
        HWREPO / "usb_data_same_net.py",
    )

    assert all(line_count(path) < IMPLEMENTATION_MAX_LINES for path in modules)
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
    assert usb_data_pair_resistive_bridge.usb_data_pair_resistive_bridge_candidates.__module__.endswith(
        "usb_data_pair_resistive_bridge"
    )
    assert (
        usb_data_pair_resistive_bridge.usb_data_pair_endpoints
        is usb_data_pair_endpoints.usb_data_pair_endpoints
    )
