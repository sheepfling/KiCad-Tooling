"""Keep BJT base-bias analysis modular and owned by the component theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.architecture]

RULE_ID = "component.bjt_base_without_visible_emitter_bias"
OWNER = "kicad_tooling/hwrepo/component_bjt_base_bias.py#bjts_without_visible_emitter_bias"


def test_base_bias_rule_has_a_bounded_theme_owner_and_shared_symbol_helper() -> None:
    owner = HWREPO / "component_bjt_base_bias.py"
    symbols = HWREPO / "component_bjt_symbols.py"
    assert owner.is_file()
    assert symbols.is_file()
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert line_count(symbols) < IMPLEMENTATION_MAX_LINES
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    assert rule.theme == "components"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs


def test_existing_bjt_checks_import_the_canonical_supported_symbol_owner() -> None:
    for module in (
        "component_bjt_base_drive.py",
        "component_bjt_terminal_order.py",
        "component_bjt_base_bias.py",
    ):
        source = (HWREPO / module).read_text(encoding="utf-8")
        assert "from .component_bjt_symbols import basic_bjt_role_numbers" in source
        assert "_SUPPORTED_SYMBOLS =" not in source
