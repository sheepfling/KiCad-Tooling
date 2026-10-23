"""Keep the MOSFET gate candidate focused and owned by the component theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.architecture]

RULE_ID = "component.mosfet_gate_without_peer"
OWNER = "kicad_tooling/hwrepo/mosfet_gate_connectivity.py#mosfet_gates_without_peer"


def test_mosfet_gate_predicate_has_a_small_theme_owned_module() -> None:
    source = HWREPO / "mosfet_gate_connectivity.py"
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert source.is_file()
    assert line_count(source) < IMPLEMENTATION_MAX_LINES
    assert rule.theme == "components"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
