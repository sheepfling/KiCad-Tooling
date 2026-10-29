"""Keep the same-voltage supply-input review in its component theme owner."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
    pytest.mark.architecture,
]

RULE_ID = "component.same_voltage_power_inputs_split"
OWNER = (
    "kicad_tooling/hwrepo/component_power_input_domains.py"
    "#same_voltage_power_inputs_on_different_nets"
)


def test_rule_has_a_small_theme_owner_and_reuses_explicit_voltage_parsing() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    modules = (
        "kicad_tooling/hwrepo/component_power_input_domains.py",
        "kicad_tooling/hwrepo/design_lint_power_candidates.py",
        "kicad_tooling/ci_hosted_component_same_voltage_power_inputs.py",
        "kicad_tooling/ci_hosted_component_same_voltage_power_inputs_lane.py",
        "tests/test_component_same_voltage_power_input_domains.py",
        "tests/design_lint_fixtures/same_voltage_power_inputs.py",
        "tests/test_component_same_voltage_power_input_native_fixture_lane.py",
        "tests/test_design_lint_mcp_parity_same_voltage_power_input.py",
    )
    sizes = {path: line_count(REPO_ROOT / path) for path in modules}

    assert rule.theme == "components"
    assert rule.default_mode == "off"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/power_rails.py#explicit_voltage_rail_value"
        in rule.implementation_refs
    )
    assert all(size < IMPLEMENTATION_MAX_LINES for size in sizes.values()), sizes
