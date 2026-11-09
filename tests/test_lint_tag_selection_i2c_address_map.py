"""Keep I2C address-map native coverage selectable as one rule-scoped gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.lint_gate_scope import (
    active_design_lint_rule_ids,
    configured_native_fixtures,
    parse_tag_message,
    required_native_fixtures_by_rule,
)

_NATIVE_FIXTURE = "KICAD_RUN_NATIVE_I2C_ADDRESS_MAP_FIXTURES"


@pytest.mark.catalog_lint
@pytest.mark.parametrize(
    "rule_id",
    (
        "bus.i2c_address_collision",
        "bus.i2c_address_mismatch",
        "bus.i2c_unmapped_responder",
    ),
)
def test_i2c_address_map_rules_select_their_shared_native_fixture(rule_id: str) -> None:
    repository = Path(__file__).resolve().parents[1]
    fixtures = configured_native_fixtures(repository)
    rule_ids = active_design_lint_rule_ids()
    required_by_rule = required_native_fixtures_by_rule()

    assert rule_id in rule_ids
    assert _NATIVE_FIXTURE in fixtures
    assert required_by_rule[rule_id] == (_NATIVE_FIXTURE,)

    scope = parse_tag_message(
        f"Focused deterministic lint gate\n\n"
        f"Lint-Rule: {rule_id}\nNative-Fixture: {_NATIVE_FIXTURE}\n",
        fixtures,
        rule_ids,
        required_by_rule,
    )

    assert scope.rule_id == rule_id
    assert scope.native_fixtures == (_NATIVE_FIXTURE,)
    assert scope.pytest_markexpr == (
        f'design_lint and (design_lint_rule(rule_id="{rule_id}") or rule_gate_integrity)'
    )
