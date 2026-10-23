"""Keep polarized-capacitor polarity analysis in its focused component owner."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import (
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    REPO_ROOT,
    line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.architecture]

RULE_ID = "component.polarized_capacitor_reversed_on_named_rails"
OWNER = (
    "kicad_tooling/hwrepo/component_polarized_capacitor_orientation.py"
    "#polarized_capacitors_on_reversed_named_rails"
)


def test_polarized_capacitor_predicate_has_a_small_theme_owned_module() -> None:
    source = HWREPO / "component_polarized_capacitor_orientation.py"
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    review_modules = (
        source,
        REPO_ROOT / "kicad_tooling/ci_hosted_polarized_capacitor.py",
        REPO_ROOT / "tests/design_lint_fixtures/polarized_capacitor.py",
        REPO_ROOT / "tests/test_polarized_capacitor_orientation.py",
        REPO_ROOT / "tests/test_polarized_capacitor_fixture_inventory.py",
        REPO_ROOT / "tests/test_polarized_capacitor_native_fixture.py",
    )

    assert source.is_file()
    sizes = {path.relative_to(REPO_ROOT): line_count(path) for path in review_modules}
    oversized = {path: size for path, size in sizes.items() if size >= IMPLEMENTATION_MAX_LINES}
    assert not oversized, f"Split polarized-capacitor lint modules below 500 lines: {oversized}"
    assert rule.theme == "components"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
