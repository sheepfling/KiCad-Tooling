"""Keep generic USB connector review tied to its theme-owned predicate."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]


def test_rule_uses_its_focused_native_pin_predicate_owner() -> None:
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "bus.usb_generic_connector_phy_pair_review"
    )

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/usb_peer_generic_connector_candidates.py"
        "#generic_usb_connector_data_pair_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
