"""Guard the boundary between project requirements and heuristic defaults."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog


def test_only_project_authored_population_requirement_defaults_to_block() -> None:
    catalog = rule_catalog()
    default_block_rules = {
        rule.rule_id: rule for rule in catalog.rules if rule.default_mode == "block"
    }

    assert set(default_block_rules) == {"pcb.required_fitted_reference"}
    rule = default_block_rules["pcb.required_fitted_reference"]
    assert "project-authored" in rule.evidence_adapter.casefold()
    assert "project-authored" in rule.predicate.casefold()
    assert "do not infer requirements" in rule.predicate.casefold()
