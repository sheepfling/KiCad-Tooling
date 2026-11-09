"""Keep SWD endpoint inventory and same-net lint in focused interface modules."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.design_lint_rule_selector_support import collect_rule_nodes

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

RULE_ID = "bus.swdio_swclk_same_net"
OWNER = "kicad_tooling/hwrepo/swd_same_net.py#swdio_swclk_same_net_candidates"
MODULES = (
    "swd_endpoint_inventory.py",
    "design_lint_swd_same_net_candidate_evidence.py",
    "swd_same_net.py",
    "bus_swd_generic_connector.py",
    "design_lint_bus_candidates.py",
)


def test_rule_owner_and_inventory_boundary_are_theme_owned() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs

    package = Path(__file__).parents[1] / "kicad_tooling/hwrepo"
    endpoint_tree = ast.parse((package / "swd_endpoint_inventory.py").read_text(encoding="utf-8"))
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "swd_function_role"
        for node in endpoint_tree.body
    )
    generic_tree = ast.parse((package / "bus_swd_generic_connector.py").read_text(encoding="utf-8"))
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "swd_endpoint_inventory"
        and any(alias.name == "swd_function_role" for alias in node.names)
        for node in generic_tree.body
    )


def test_swd_same_net_modules_stay_below_review_limit() -> None:
    package = Path(__file__).parents[1] / "kicad_tooling/hwrepo"
    counts = {
        name: len((package / name).read_text(encoding="utf-8").splitlines()) for name in MODULES
    }

    assert all(count < 500 for count in counts.values()), counts


def test_rule_selector_collects_fault_parity_and_native_cases() -> None:
    result = collect_rule_nodes(RULE_ID)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "tests/test_swd_signal_same_net.py::"
        "test_unique_native_swd_pair_on_one_net_emits_review_with_exact_evidence"
    ) in result.stdout
    assert (
        "tests/test_design_lint_mcp_parity_swd_signal_same_net.py::"
        "test_swd_signal_same_net_cli_mcp_parity"
    ) in result.stdout
    assert (
        "tests/test_swd_signal_same_net_native_fixture_lane.py::"
        "test_native_swdio_swclk_same_net_fault_and_control_repeat"
    ) in result.stdout
