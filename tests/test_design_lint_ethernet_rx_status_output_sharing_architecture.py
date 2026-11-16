"""Keep Ethernet PHY RX status lint tied to its typed owner and native lane."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

RULE_ID = "bus.ethernet_rx_status_outputs_share_net"
NATIVE_FIXTURE = "KICAD_RUN_NATIVE_ETHERNET_RX_OUTPUT_SHARING_FIXTURES"
NATIVE_TEST = (
    "tests.test_ethernet_rx_output_sharing_native_fixture_lane."
    "test_native_ethernet_rx_output_sharing_fault_and_control_repeat"
)
REPOSITORY = Path(__file__).parents[1]

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.catalog_lint,
    pytest.mark.architecture,
]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ethernet_rx_status_rule_catalog_and_owner_boundaries() -> None:
    rule = next(entry for entry in rule_catalog().rules if entry.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/ethernet_rx_status_output_sharing.py#"
        "ethernet_rx_status_output_sharing_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/ethernet_phy_identity.py#explicit_ethernet_phy_identity"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/signal_pair_output_sharing.py#signal_output_sharing_groups"
        in rule.implementation_refs
    )
    assert rule.required_native_fixtures == (NATIVE_FIXTURE,)
    assert NATIVE_TEST in rule.fault_fixtures
    assert NATIVE_TEST in rule.valid_control_fixtures

    owner = REPOSITORY / "kicad_tooling/hwrepo/ethernet_rx_status_output_sharing.py"
    identity = REPOSITORY / "kicad_tooling/hwrepo/ethernet_phy_identity.py"
    coordinator = REPOSITORY / "kicad_tooling/hwrepo/design_lint_bus_candidates.py"
    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert len(identity.read_text(encoding="utf-8").splitlines()) < 500
    assert "from .ethernet_rx_status_output_sharing import " in coordinator.read_text(
        encoding="utf-8"
    )
