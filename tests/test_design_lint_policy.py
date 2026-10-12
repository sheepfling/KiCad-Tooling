"""Pytest regressions for project-configured design-lint policy."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintRuleOverride
from tests.design_lint_fixtures import coach, multiconductor_connector, observed

pytestmark = pytest.mark.design_lint


@pytest.mark.connector_lint
@pytest.mark.return_path_lint
def test_rule_overrides_block_or_turn_off_with_reason() -> None:
    blocked = evaluate(
        "synthetic-ports",
        coach(observed()),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="connector.repeated_pin_function",
                    mode="block",
                    reason="Port pin discrepancies require release review",
                ),
            ),
        ),
    )
    assert blocked.status == "FAIL"

    off = evaluate(
        "synthetic-ports",
        coach(observed()),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="connector.repeated_pin_function",
                    mode="off",
                    reason="This synthetic board uses independent port rails",
                ),
                DesignLintRuleOverride(
                    rule_id="net.numbered_returns",
                    mode="off",
                    reason="This synthetic board uses isolated returns",
                ),
            ),
        ),
    )
    assert off.status == "PASS"
    assert all(item.disposition == "RULE_OFF" for item in off.findings)
    assert all(item.reason for item in off.findings)


@pytest.mark.connector_lint
def test_connector_return_coverage_rule_can_be_configured() -> None:
    observed_connector = multiconductor_connector(return_named=False)
    blocked = evaluate(
        "synthetic-ports",
        coach(observed_connector),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="connector.no_connected_return",
                    mode="block",
                    reason="Port pinout requires a signal return decision",
                ),
            ),
        ),
    )
    assert blocked.status == "FAIL"

    ignored_by_rule = evaluate(
        "synthetic-ports",
        coach(observed_connector),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="connector.no_connected_return",
                    mode="off",
                    reason="All ports use a reviewed isolated interface",
                ),
            ),
        ),
    )
    assert ignored_by_rule.status == "PASS"
    assert ignored_by_rule.findings[0].disposition == "RULE_OFF"


def test_invalid_or_duplicate_decisions_fail_schema() -> None:
    with pytest.raises(ValidationError):
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(rule_id="net.numbered_returns", mode="off", reason="first"),
                DesignLintRuleOverride(
                    rule_id="net.numbered_returns",
                    mode="block",
                    reason="second",
                ),
            )
        )

    with pytest.raises(ValidationError):
        DesignLintRuleOverride.model_validate(
            {"rule_id": "net.numbered_returns", "mode": "off", "reason": ""}
        )
