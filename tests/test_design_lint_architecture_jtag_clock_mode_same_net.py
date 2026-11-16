"""Keep JTAG TCK/TMS same-net lint source-bound and selectable."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.design_lint_rule_selector_support import collect_rule_nodes

RULE_ID = "bus.jtag_tck_tms_same_net"
OWNER = "kicad_tooling/hwrepo/jtag_clock_mode_same_net.py#jtag_tck_tms_same_net_candidates"
NATIVE_TEST = (
    "tests.test_jtag_clock_mode_same_net_native_fixture_lane."
    "test_native_jtag_clock_mode_same_net_fault_and_control_repeat"
)
REPOSITORY = Path(__file__).parents[1]

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.catalog_lint,
    pytest.mark.architecture,
]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_owns_synthetic_native_parity_and_metamorphic_cases() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.default_mode == "review"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert rule.required_native_fixtures == ("KICAD_RUN_NATIVE_JTAG_CLOCK_MODE_SAME_NET_FIXTURES",)
    assert NATIVE_TEST in rule.fault_fixtures
    assert NATIVE_TEST in rule.valid_control_fixtures
    assert (
        "kicad_tooling/hwrepo/jtag_signal_inventory.py#JtagEndpointInventory.named_rail_signal_pins"
        in rule.implementation_refs
    )

    selection = collect_rule_nodes(RULE_ID)
    assert selection.returncode == 0, selection.stdout + selection.stderr
    assert (
        "tests/test_jtag_clock_mode_same_net.py::"
        "test_mapping_order_preserves_fingerprint_and_separation_repairs_candidate"
    ) in selection.stdout
    assert (
        "tests/test_design_lint_mcp_parity_jtag_clock_mode_same_net.py::"
        "test_jtag_clock_mode_same_net_cli_mcp_parity"
    ) in selection.stdout
    assert NATIVE_TEST.rsplit(".", 1)[-1] in selection.stdout


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_owner_and_bus_coordinator_stay_below_module_review_limit() -> None:
    owner = REPOSITORY / "kicad_tooling/hwrepo/jtag_clock_mode_same_net.py"
    coordinator = REPOSITORY / "kicad_tooling/hwrepo/design_lint_bus_candidates.py"
    inventory = REPOSITORY / "kicad_tooling/hwrepo/jtag_signal_inventory.py"

    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert len(coordinator.read_text(encoding="utf-8").splitlines()) < 500
    assert len(inventory.read_text(encoding="utf-8").splitlines()) < 500
    assert "from .jtag_clock_mode_same_net import " in coordinator.read_text(encoding="utf-8")
