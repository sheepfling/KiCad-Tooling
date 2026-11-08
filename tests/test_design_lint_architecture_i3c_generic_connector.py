"""Keep generic I3C connector review in focused interface modules."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import i3c_generic_connector_candidates
from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

RULE_ID = "bus.i3c_generic_connector_pair_review"
OWNER = "kicad_tooling/hwrepo/i3c_generic_connector_candidates.py#generic_i3c_connector_pairs"
MODULES = (
    "i3c_endpoint_pairs.py",
    "i3c_connector_map.py",
    "i3c_generic_connector_candidates.py",
    "i3c_generic_connector_models.py",
    "design_lint_i3c_generic_connector_candidate_evidence.py",
    "design_lint_i3c_generic_connector_candidates.py",
    "design_lint_i3c_bus_candidates.py",
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_has_a_theme_owned_predicate_and_shared_endpoint_helpers() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/i3c_endpoint_pairs.py#i3c_endpoint_pairs" in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/i3c_connector_map.py#i3c_source_map_covers_role"
        in rule.implementation_refs
    )
    assert i3c_generic_connector_candidates.generic_i3c_connector_pairs.__module__.endswith(
        "i3c_generic_connector_candidates"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_i3c_generic_connector_modules_stay_below_review_limit() -> None:
    counts = {name: line_count(HWREPO / name) for name in MODULES}

    assert len(counts) == len(MODULES)
    assert all(count < IMPLEMENTATION_MAX_LINES for count in counts.values()), counts


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_i3c_theme_dispatcher_delegates_without_owning_the_predicate() -> None:
    path = HWREPO / "design_lint_i3c_bus_candidates.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "generic_i3c_connector_pair_review_candidates" in calls
    assert "generic_i3c_connector_pairs" not in calls
