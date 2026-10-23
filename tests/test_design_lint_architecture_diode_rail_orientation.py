"""Keep diode rail review in a small component-owned implementation."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.architecture]

RULE_ID = "component.diode_anode_below_cathode_on_named_rails"
OWNER = (
    "kicad_tooling/hwrepo/component_diode_rail_orientation.py"
    "#diodes_with_anode_below_cathode_on_named_rails"
)


def test_rule_owner_fixture_service_and_regressions_stay_below_review_limit() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    modules = (
        "kicad_tooling/hwrepo/component_rail_potentials.py",
        "kicad_tooling/hwrepo/component_diode_rail_orientation.py",
        "kicad_tooling/ci_hosted_component_lint.py",
        "kicad_tooling/ci_hosted_diode_rail_orientation.py",
        "tests/design_lint_fixtures/diode_rail_orientation.py",
        "tests/test_diode_rail_orientation.py",
        "tests/test_diode_rail_orientation_native_fixture.py",
        "tests/test_diode_rail_fixture_inventory.py",
        "tests/test_design_lint_architecture_diode_rail_orientation.py",
    )
    sizes = {path: line_count(REPO_ROOT / path) for path in modules}

    assert rule.theme == "components"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert {
        "kicad_tooling/hwrepo/component_rail_potentials.py#named_net_potential",
        "kicad_tooling/hwrepo/component_rail_potentials.py#potential_is_lower",
    } <= set(rule.implementation_refs)
    assert all(size < IMPLEMENTATION_MAX_LINES for size in sizes.values()), sizes
