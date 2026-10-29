"""Guard the focused owner for USB-C CC endpoint-pairing review."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]


def test_crossed_cc_rule_uses_a_small_theme_owned_predicate() -> None:
    owner = "kicad_tooling/hwrepo/usb_c_cc_endpoint_pairing.py#crossed_usb_c_cc_endpoint_candidates"
    rule = next(
        item for item in rule_catalog().rules if item.rule_id == "bus.usb_c_cc_endpoint_crossed"
    )

    assert line_count(HWREPO / "usb_c_cc_endpoint_pairing.py") < IMPLEMENTATION_MAX_LINES
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
