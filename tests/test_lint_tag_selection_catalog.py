"""Keep rule-scoped prerelease tags tied to native fixture declarations."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.lint_gate_scope import (
    active_design_lint_rule_ids,
    configured_native_fixtures,
    parse_tag_message,
    required_native_fixtures_by_rule,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.catalog_lint]

_NATIVE_FIXTURE_CASES = tuple(
    pytest.param(rule_id, fixture, id=f"{rule_id}:{fixture}")
    for rule_id, fixtures in sorted(required_native_fixtures_by_rule().items())
    for fixture in sorted(fixtures)
)


@pytest.mark.rule_gate_integrity
@pytest.mark.parametrize(("rule_id", "native_fixture"), _NATIVE_FIXTURE_CASES)
def test_lint_tag_selects_rule_and_all_its_configured_native_fixtures(
    rule_id: str,
    native_fixture: str,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    fixtures = configured_native_fixtures(repository)
    rule_ids = active_design_lint_rule_ids()
    required_by_rule = required_native_fixtures_by_rule()
    assert rule_id in rule_ids
    assert native_fixture in fixtures
    required_fixtures = required_by_rule[rule_id]
    assert native_fixture in required_fixtures
    assert set(required_fixtures) <= fixtures
    native_fixture_lines = "".join(f"Native-Fixture: {item}\n" for item in required_fixtures)

    scope = parse_tag_message(
        f"Focused deterministic lint gate\n\nLint-Rule: {rule_id}\n{native_fixture_lines}",
        fixtures,
        rule_ids,
        required_by_rule,
    )

    assert scope.area is None
    assert scope.rule_id == rule_id
    assert scope.pytest_markexpr == (
        f'design_lint and (design_lint_rule(rule_id="{rule_id}") or rule_gate_integrity)'
    )
    assert scope.native_fixtures == required_fixtures
