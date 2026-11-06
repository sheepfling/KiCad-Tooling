"""Pin-level reporting for existing Ethernet complementary-pair findings."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates
from tests.design_lint_fixtures.ethernet_data_pair_same_net import (
    ethernet_data_pair_same_net_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.complementary_pair_assignment"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ethernet_same_net_pair_finding_names_pins_and_net() -> None:
    fault = ethernet_data_pair_same_net_netlist(shared_direction="RX")
    control = ethernet_data_pair_same_net_netlist(shared_direction=None)

    findings = tuple(item for item in candidates(fault) if item.rule_id == RULE_ID)
    assert len(findings) == 1
    assert findings[0].subject == "U1: Ethernet RX pair U1.3/U1.4 share ETH_RX_SHARED"
    assert findings[0].evidence == {
        "positive_pins": ("U1.3",),
        "negative_pins": ("U1.4",),
        "positive_nets": ("ETH_RX_SHARED",),
        "negative_nets": ("ETH_RX_SHARED",),
    }
    assert "both resolve to one schematic net (ETH_RX_SHARED)" in findings[0].message
    assert not tuple(item for item in candidates(control) if item.rule_id == RULE_ID)
