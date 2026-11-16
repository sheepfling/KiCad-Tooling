"""Keep MII TX-clock sharing in its owning interface module."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

RULE_ID = "bus.ethernet_tx_clock_outputs_share_net"
OWNER = (
    "kicad_tooling/hwrepo/ethernet_tx_clock_output_sharing.py#"
    "ethernet_tx_clock_output_sharing_candidates"
)
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
def test_catalog_owns_tx_clock_rule_and_native_fault_control() -> None:
    rule = next(entry for entry in rule_catalog().rules if entry.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.default_mode == "review"
    assert rule.implementation_owner == OWNER
    assert rule.implementation_owner in rule.implementation_refs
    assert rule.required_native_fixtures == (NATIVE_FIXTURE,)
    assert NATIVE_TEST in rule.fault_fixtures
    assert NATIVE_TEST in rule.valid_control_fixtures
    assert (
        "kicad_tooling/hwrepo/ethernet_tx_clock_output_sharing.py#ethernet_phy_tx_clock_output_role"
    ) in rule.implementation_refs

    owner = REPOSITORY / "kicad_tooling/hwrepo/ethernet_tx_clock_output_sharing.py"
    coordinator = REPOSITORY / "kicad_tooling/hwrepo/design_lint_bus_candidates.py"
    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert "from .ethernet_tx_clock_output_sharing import " in coordinator.read_text(
        encoding="utf-8"
    )
