"""Keep USB-C VBUS review logic in its focused protocol owner."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo import usb_c_vbus_review
from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

RULE_ID = "bus.usb_c_vbus_capacitance_review"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_usb_c_vbus_capacitance_review_uses_focused_protocol_owner() -> None:
    owner = "kicad_tooling/hwrepo/usb_c_vbus_review.py#usb_c_vbus_capacitance_gaps"
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert line_count(HWREPO / "usb_c_vbus_review.py") < IMPLEMENTATION_MAX_LINES
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
    assert usb_c_vbus_review.usb_c_vbus_capacitance_gaps.__module__.endswith("usb_c_vbus_review")
