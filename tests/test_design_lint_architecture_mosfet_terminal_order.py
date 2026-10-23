"""Keep MOSFET terminal-order review inside a focused component owner."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.architecture]

RULE_ID = "component.mosfet_terminal_order_on_named_rails"
OWNER = (
    "kicad_tooling/hwrepo/component_mosfet_terminal_order.py"
    "#mosfets_with_unusual_drain_source_rail_order"
)


def test_rule_owner_and_shared_symbol_inventory_stay_focused() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    modules = (
        "kicad_tooling/hwrepo/component_mosfet_symbols.py",
        "kicad_tooling/hwrepo/component_mosfet_terminal_order.py",
        "kicad_tooling/hwrepo/component_rail_potentials.py",
        "kicad_tooling/hwrepo/mosfet_gate_connectivity.py",
        "kicad_tooling/hwrepo/design_lint_component_candidates.py",
        "kicad_tooling/ci_hosted_mosfet_gate_fixture.py",
        "tests/design_lint_fixtures/mosfet_terminal_order.py",
        "tests/test_mosfet_terminal_order.py",
        "tests/test_mosfet_terminal_order_native_fixture.py",
        "tests/test_design_lint_architecture_mosfet_terminal_order.py",
    )
    sizes = {path: line_count(REPO_ROOT / path) for path in modules}

    assert rule.theme == "components"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert {
        "kicad_tooling/hwrepo/component_mosfet_symbols.py#mosfet_channel_type",
        "kicad_tooling/hwrepo/component_rail_potentials.py#named_net_potential",
        "kicad_tooling/hwrepo/component_rail_potentials.py#potential_is_lower",
    } <= set(rule.implementation_refs)
    assert all(size < IMPLEMENTATION_MAX_LINES for size in sizes.values()), sizes


def test_gate_and_terminal_rules_share_one_allowlisted_mosfet_identity_service() -> None:
    symbols = REPO_ROOT / "kicad_tooling/hwrepo/component_mosfet_symbols.py"
    gate = (REPO_ROOT / "kicad_tooling/hwrepo/mosfet_gate_connectivity.py").read_text(
        encoding="utf-8"
    )
    terminal_order = (
        REPO_ROOT / "kicad_tooling/hwrepo/component_mosfet_terminal_order.py"
    ).read_text(encoding="utf-8")

    assert symbols.is_file()
    assert "from .component_mosfet_symbols import SUPPORTED_THREE_TERMINAL_MOSFET_SYMBOLS" in gate
    assert "from .component_mosfet_symbols import mosfet_channel_type" in terminal_order
    assert "_SUPPORTED_SYMBOLS = frozenset" not in gate
