"""Guard the USB-C SuperSpeed lane-label rule's focused owner boundary."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import (
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]


def test_usb_c_superspeed_lane_label_rule_uses_a_focused_predicate_owner() -> None:
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "bus.usb_c_superspeed_lane_label_mismatch"
    )
    owner = HWREPO / "usb_c_superspeed_lane_labels.py"

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/usb_c_superspeed_lane_labels.py#"
        "usb_c_superspeed_lane_label_mismatch_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/bus_signal_pairs.py#usb_c_superspeed_lane_function_role"
        in rule.implementation_refs
    )
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
