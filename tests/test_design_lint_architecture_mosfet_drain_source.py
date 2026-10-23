"""Keep MOSFET main-terminal review in a small component owner."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.architecture]

RULE_ID = "component.mosfet_drain_source_same_net"
GATE_SOURCE_RULE_ID = "component.mosfet_gate_source_same_net"
OWNER = (
    "kicad_tooling/hwrepo/design_lint_component_mosfet_terminals.py"
    "#mosfets_with_drain_source_on_same_net"
)


def test_rule_owner_uses_shared_mosfet_roles_and_stays_focused() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    modules = (
        "kicad_tooling/hwrepo/design_lint_component_mosfet_terminals.py",
        "kicad_tooling/hwrepo/component_mosfet_symbols.py",
        "kicad_tooling/hwrepo/component_mosfet_terminal_order.py",
        "kicad_tooling/hwrepo/design_lint_component_candidates.py",
        "kicad_tooling/ci_hosted_component_mosfet_terminals.py",
        "kicad_tooling/ci_hosted_mosfet_gate_fixture.py",
        "kicad_tooling/ci_hosted_support.py",
        "tests/design_lint_fixtures/mosfet_drain_source_same_net.py",
        "tests/design_lint_fixtures/mosfet_gate_source_same_net.py",
        "tests/test_mosfet_drain_source_same_net.py",
        "tests/test_mosfet_gate_source_same_net.py",
        "tests/test_mosfet_drain_source_same_net_native_fixture.py",
        "tests/test_design_lint_determinism_mosfet_drain_source.py",
        "tests/test_design_lint_architecture_mosfet_drain_source.py",
    )
    sizes = {path: line_count(REPO_ROOT / path) for path in modules}

    assert rule.theme == "components"
    assert rule.default_mode == "off"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/component_mosfet_symbols.py#mosfet_terminal_role_numbers"
        in rule.implementation_refs
    )
    assert rule.required_native_fixtures == ("KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES",)
    assert all(size < IMPLEMENTATION_MAX_LINES for size in sizes.values()), sizes


def test_shared_terminal_role_service_is_used_by_the_existing_order_rule() -> None:
    terminal_order = (
        REPO_ROOT / "kicad_tooling/hwrepo/component_mosfet_terminal_order.py"
    ).read_text(encoding="utf-8")
    topology = (
        REPO_ROOT / "kicad_tooling/hwrepo/design_lint_component_mosfet_terminals.py"
    ).read_text(encoding="utf-8")

    assert "mosfet_terminal_role_numbers" in terminal_order
    assert "mosfet_terminal_role_numbers" in topology
    assert "_TERMINAL_FUNCTIONS" not in terminal_order


def test_gate_source_same_net_rule_uses_shared_roles_and_keeps_default_off() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == GATE_SOURCE_RULE_ID)
    owner = (
        "kicad_tooling/hwrepo/design_lint_component_mosfet_terminals.py"
        "#mosfets_with_gate_source_on_same_net"
    )
    source = REPO_ROOT / "kicad_tooling/hwrepo/design_lint_component_mosfet_terminals.py"

    assert rule.theme == "components"
    assert rule.default_mode == "off"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/component_mosfet_symbols.py#mosfet_terminal_role_numbers"
        in rule.implementation_refs
    )
    assert rule.required_native_fixtures == ("KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES",)
    assert line_count(source) < IMPLEMENTATION_MAX_LINES
