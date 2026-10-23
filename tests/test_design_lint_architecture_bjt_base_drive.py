"""Keep BJT base-drive review in its own focused component implementation."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.architecture]

RULE_ID = "component.bjt_base_direct_drive"
OWNER = "kicad_tooling/hwrepo/component_bjt_base_drive.py#bjts_with_direct_output_base_drive"


def test_rule_owner_is_theme_scoped_and_stays_below_review_limits() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    modules = (
        "kicad_tooling/hwrepo/component_bjt_base_drive.py",
        "kicad_tooling/hwrepo/component_pin_types.py",
        "kicad_tooling/hwrepo/design_lint_component_candidates.py",
        "tests/design_lint_fixtures/bjt_base_drive.py",
        "tests/test_bjt_base_drive.py",
        "tests/test_design_lint_architecture_bjt_base_drive.py",
    )
    sizes = {path: line_count(REPO_ROOT / path) for path in modules}

    assert rule.theme == "components"
    assert rule.default_mode == "review"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/component_pin_types.py#is_output_capable_pin_type"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/design_lint_component_candidates.py#component_candidates"
        in rule.implementation_refs
    )
    assert all(size < IMPLEMENTATION_MAX_LINES for size in sizes.values()), sizes
