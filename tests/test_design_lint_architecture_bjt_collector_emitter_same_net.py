"""Keep BJT terminal same-net reviews in a focused component implementation."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.architecture]

RULE_ID = "component.bjt_collector_emitter_same_net"
OWNER = (
    "kicad_tooling/hwrepo/design_lint_component_bjt_terminals.py"
    "#bjts_with_collector_emitter_on_same_net"
)


def test_rule_owner_reuses_shared_bjt_roles_and_stays_small() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    modules = (
        "kicad_tooling/hwrepo/design_lint_component_bjt_terminals.py",
        "kicad_tooling/hwrepo/component_bjt_symbols.py",
        "kicad_tooling/hwrepo/design_lint_component_candidates.py",
        "tests/design_lint_fixtures/bjt_collector_emitter_same_net.py",
        "tests/test_bjt_base_emitter_same_net.py",
        "tests/test_bjt_collector_emitter_same_net.py",
        "tests/test_bjt_terminal_order_native_fixture.py",
        "tests/test_design_lint_architecture_bjt_collector_emitter_same_net.py",
    )
    sizes = {path: line_count(REPO_ROOT / path) for path in modules}

    assert rule.theme == "components"
    assert rule.default_mode == "off"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/component_bjt_symbols.py#basic_bjt_role_numbers"
        in rule.implementation_refs
    )
    assert rule.required_native_fixtures == ("KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES",)
    assert all(size < IMPLEMENTATION_MAX_LINES for size in sizes.values()), sizes


def test_base_emitter_rule_owner_reuses_shared_bjt_roles_and_stays_small() -> None:
    rule_id = "component.bjt_base_emitter_same_net"
    owner = (
        "kicad_tooling/hwrepo/design_lint_component_bjt_terminals.py"
        "#bjts_with_base_emitter_on_same_net"
    )
    rule = next(item for item in rule_catalog().rules if item.rule_id == rule_id)
    modules = (
        "kicad_tooling/hwrepo/design_lint_component_bjt_terminals.py",
        "kicad_tooling/hwrepo/component_bjt_symbols.py",
        "kicad_tooling/hwrepo/design_lint_component_candidates.py",
        "tests/design_lint_fixtures/bjt_collector_emitter_same_net.py",
        "tests/test_bjt_base_emitter_same_net.py",
        "tests/test_bjt_terminal_order_native_fixture.py",
        "tests/test_design_lint_architecture_bjt_collector_emitter_same_net.py",
    )
    sizes = {path: line_count(REPO_ROOT / path) for path in modules}

    assert rule.theme == "components"
    assert rule.default_mode == "off"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/component_bjt_symbols.py#basic_bjt_role_numbers"
        in rule.implementation_refs
    )
    assert rule.required_native_fixtures == ("KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES",)
    assert all(size < IMPLEMENTATION_MAX_LINES for size in sizes.values()), sizes


def test_base_collector_rule_owner_reuses_shared_bjt_roles_and_stays_small() -> None:
    rule_id = "component.bjt_base_collector_same_net"
    owner = (
        "kicad_tooling/hwrepo/design_lint_component_bjt_terminals.py"
        "#bjts_with_base_collector_on_same_net"
    )
    rule = next(item for item in rule_catalog().rules if item.rule_id == rule_id)
    modules = (
        "kicad_tooling/hwrepo/design_lint_component_bjt_terminals.py",
        "kicad_tooling/hwrepo/component_bjt_symbols.py",
        "kicad_tooling/hwrepo/design_lint_component_candidates.py",
        "tests/design_lint_fixtures/bjt_collector_emitter_same_net.py",
        "tests/test_bjt_base_collector_same_net.py",
        "tests/test_bjt_base_collector_same_net_native_fixture.py",
        "tests/test_design_lint_architecture_bjt_collector_emitter_same_net.py",
    )
    sizes = {path: line_count(REPO_ROOT / path) for path in modules}

    assert rule.theme == "components"
    assert rule.default_mode == "off"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/component_bjt_symbols.py#basic_bjt_role_numbers"
        in rule.implementation_refs
    )
    assert rule.required_native_fixtures == ("KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES",)
    assert all(size < IMPLEMENTATION_MAX_LINES for size in sizes.values()), sizes
