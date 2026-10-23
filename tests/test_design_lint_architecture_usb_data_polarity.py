"""Guard USB data polarity rule ownership and source boundaries."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]


def test_usb_data_polarity_rule_points_to_its_interface_owner() -> None:
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "bus.usb_data_polarity_label_mismatch"
    )

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/design_lint_interfaces_usb_data_polarity.py#"
        "usb_data_polarity_label_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
