"""Keep BJT rail-order review in a focused component implementation."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.architecture]

RULE_ID = "component.bjt_terminal_order_on_named_rails"
OWNER = (
    "kicad_tooling/hwrepo/component_bjt_terminal_order.py"
    "#bjts_with_unusual_collector_emitter_rail_order"
)


def test_rule_owner_reuses_shared_rail_evidence_and_stays_small() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    modules = (
        "kicad_tooling/hwrepo/component_bjt_terminal_order.py",
        "kicad_tooling/hwrepo/component_rail_potentials.py",
        "kicad_tooling/hwrepo/design_lint_component_candidates.py",
        "tests/design_lint_fixtures/bjt_terminal_order.py",
        "tests/test_bjt_terminal_order.py",
        "tests/test_bjt_terminal_order_native_fixture.py",
        "tests/test_design_lint_architecture_bjt_terminal_order.py",
    )
    sizes = {path: line_count(REPO_ROOT / path) for path in modules}

    assert rule.theme == "components"
    assert rule.default_mode == "off"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert {
        "kicad_tooling/hwrepo/component_rail_potentials.py#named_net_potential",
        "kicad_tooling/hwrepo/component_rail_potentials.py#potential_is_lower",
    } <= set(rule.implementation_refs)
    assert all(size < IMPLEMENTATION_MAX_LINES for size in sizes.values()), sizes
