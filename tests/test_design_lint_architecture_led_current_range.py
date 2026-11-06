"""Keep the mapped LED current rule in a focused component-owned service."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.architecture,
]

RULE_ID = "component.mapped_led_current_range_mismatch"
OWNER = "kicad_tooling/hwrepo/led_current_range.py#evaluate_led_current_requirement"


def test_led_current_range_rule_has_a_theme_owned_predicate_and_shared_routes() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    owner_path, owner_function = OWNER.split("#", maxsplit=1)
    owner_source = (REPO_ROOT / owner_path).read_text(encoding="utf-8")
    component_source = (
        REPO_ROOT / "kicad_tooling/hwrepo/design_lint_component_candidates.py"
    ).read_text(encoding="utf-8")
    coverage_source = (
        REPO_ROOT / "kicad_tooling/hwrepo/design_lint_mapped_topology_coverage.py"
    ).read_text(encoding="utf-8")

    assert rule.theme == "components"
    assert rule.default_mode == "review"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert f"def {owner_function}(" in owner_source
    assert "from .design_lint_led_current_candidates import led_current_range_candidates" in (
        component_source
    )
    assert "component.mapped_led_current_range_mismatch" in coverage_source


def test_led_current_rule_and_regression_modules_stay_below_review_threshold() -> None:
    paths = (
        "kicad_tooling/hwrepo/led_current_models.py",
        "kicad_tooling/hwrepo/led_current_range.py",
        "kicad_tooling/hwrepo/design_lint_led_current_candidates.py",
        "tests/design_lint_fixtures/led_current.py",
        "tests/test_led_current_range.py",
        "tests/test_led_current_native_fixture_lane.py",
        "tests/test_design_lint_mcp_parity_led_current.py",
    )
    oversized = {
        path: line_count(REPO_ROOT / path)
        for path in paths
        if line_count(REPO_ROOT / path) >= IMPLEMENTATION_MAX_LINES
    }

    assert not oversized
