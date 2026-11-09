"""Keep I2S same-net lint focused and selectable as one interface rule."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.design_lint_rule_selector_support import collect_rule_nodes

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

RULE_ID = "bus.i2s_clock_frame_same_net"
OWNER = "kicad_tooling/hwrepo/i2s_same_net.py#i2s_clock_frame_same_net_candidates"


def test_rule_uses_the_i2s_interface_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs


def test_rule_selector_collects_synthetic_parity_and_native_cases() -> None:
    result = collect_rule_nodes(RULE_ID)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "tests/test_i2s_clock_frame_same_net.py::"
        "test_shared_native_i2s_clock_roles_emit_review_with_exact_evidence"
    ) in result.stdout
    assert (
        "tests/test_design_lint_mcp_parity_i2s_clock_frame_same_net.py::"
        "test_i2s_clock_frame_same_net_cli_mcp_parity"
    ) in result.stdout
    assert (
        "tests/test_i2s_clock_frame_same_net_native_fixture_lane.py::"
        "test_native_i2s_clock_frame_same_net_fault_and_control_repeat"
    ) in result.stdout
