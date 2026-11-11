"""Keep current catalog totals in user-facing design-lint summaries accurate."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.catalog_lint]

_DOCS = Path(__file__).resolve().parents[1] / "docs"


@pytest.mark.rule_gate_integrity
def test_documented_current_catalog_totals_match_packaged_catalog() -> None:
    active_rules = tuple(rule for rule in rule_catalog().rules if rule.status == "active")
    mode_counts = Counter(rule.default_mode for rule in active_rules)
    active_count = len(active_rules)

    lint_guide = (_DOCS / "DESIGN_LINT.md").read_text(encoding="utf-8")
    cohort_trials = (_DOCS / "DESIGN_LINT_COHORT_TRIALS.md").read_text(encoding="utf-8")

    assert f"The catalog currently contains {active_count} active rules." in lint_guide
    assert (
        f"contains {active_count} active rules. Each entry has a deterministic predicate"
        in cohort_trials
    )
    assert (
        f"Of the {active_count} active rules, {mode_counts['review']} default to `review`, "
        f"{mode_counts['off']} to `off`, and\n`pcb.required_fitted_reference` to `block`."
        in cohort_trials
    )
