"""Keep the generic CAN connector heuristic in focused theme modules."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

RULE_ID = "bus.can_generic_connector_pair_review"
MODULES = (
    "can_generic_connector_models.py",
    "can_generic_connector_candidates.py",
    "design_lint_can_generic_connector_candidates.py",
    "design_lint_can_generic_connector_candidate_evidence.py",
)


def test_rule_predicate_has_a_protocol_owned_implementation() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/can_generic_connector_candidates.py#generic_can_connector_pairs"
    )
    assert rule.implementation_owner in rule.implementation_refs


def test_can_generic_connector_modules_stay_below_review_limit() -> None:
    package = Path(__file__).parents[1] / "kicad_tooling/hwrepo"
    counts = {
        name: len((package / name).read_text(encoding="utf-8").splitlines()) for name in MODULES
    }

    assert all(count < 500 for count in counts.values()), counts
