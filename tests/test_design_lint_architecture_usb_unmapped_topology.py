"""Keep USB unmapped-topology lint in its theme-owned source boundary."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]


def test_usb_unmapped_multi_pin_rule_points_to_its_topology_predicate() -> None:
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "bus.usb_unmapped_multi_pin_topology"
    )
    owner = "kicad_tooling/hwrepo/usb_peer_unsupported_topology.py#unsupported_usb_multi_pin_path_candidates"

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
    assert line_count(HWREPO / "usb_peer_unsupported_topology.py") < IMPLEMENTATION_MAX_LINES
    assert line_count(HWREPO / "design_lint_usb_unmapped_topology.py") < IMPLEMENTATION_MAX_LINES
