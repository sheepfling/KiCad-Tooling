"""Keep the MOSFET gate candidate focused and owned by the component theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.architecture]

RULE_ID = "component.mosfet_gate_without_peer"
RULE_OWNERS = {
    "component.mosfet_gate_without_peer": (
        "kicad_tooling/hwrepo/mosfet_gate_connectivity.py#mosfet_gates_without_peer"
    ),
    "component.mosfet_gate_without_visible_source_bias": (
        "kicad_tooling/hwrepo/mosfet_gate_connectivity.py#mosfet_gates_without_visible_source_bias"
    ),
    "component.mosfet_gate_direct_drive": (
        "kicad_tooling/hwrepo/component_mosfet_gate_drive.py#mosfets_with_direct_output_gate_drive"
    ),
}


def test_mosfet_gate_predicate_has_a_small_theme_owned_module() -> None:
    source = HWREPO / "mosfet_gate_connectivity.py"
    direct_drive_source = HWREPO / "component_mosfet_gate_drive.py"
    pin_type_source = HWREPO / "component_pin_types.py"
    rules = {item.rule_id: item for item in rule_catalog().rules}

    assert source.is_file()
    assert line_count(source) < IMPLEMENTATION_MAX_LINES
    assert direct_drive_source.is_file()
    assert line_count(direct_drive_source) < IMPLEMENTATION_MAX_LINES
    assert pin_type_source.is_file()
    assert line_count(pin_type_source) < IMPLEMENTATION_MAX_LINES
    assert RULE_ID in RULE_OWNERS
    for rule_id, owner in RULE_OWNERS.items():
        rule = rules[rule_id]
        assert rule.theme == "components"
        assert rule.implementation_owner == owner
        assert owner in rule.implementation_refs
