"""Keep the Ethernet management same-net predicate in its theme-owned module."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo import bus_ethernet_management_same_net
from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

OWNER = (
    "kicad_tooling/hwrepo/bus_ethernet_management_same_net.py#"
    "ethernet_management_same_net_candidates"
)
RULE_ID = "bus.ethernet_management_same_net"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
]


def test_rule_uses_a_focused_ethernet_management_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert line_count(HWREPO / "bus_ethernet_management_same_net.py") < IMPLEMENTATION_MAX_LINES
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert bus_ethernet_management_same_net.ethernet_management_same_net_candidates.__module__.endswith(
        "bus_ethernet_management_same_net"
    )
    assert rule.required_native_fixtures == (
        "KICAD_RUN_NATIVE_ETHERNET_MANAGEMENT_SAME_NET_FIXTURES",
    )
