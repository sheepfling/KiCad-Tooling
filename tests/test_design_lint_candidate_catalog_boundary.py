"""Catalog validation after every design-lint candidate source has run."""

from __future__ import annotations

from typing import cast

import pytest

from kicad_tooling.hwrepo import design_lint_evaluation_candidates
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_rule_types import DesignLintRuleId
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach, observed

pytestmark = [pytest.mark.design_lint, pytest.mark.catalog_lint]


@pytest.mark.parametrize("source", ("theme", "native_sidecar"))
def test_appended_candidate_sources_require_an_active_catalog_rule(
    monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    unknown = Candidate(
        rule_id=cast(DesignLintRuleId, "power.uncatalogued_extension"),
        subject="synthetic uncatalogued candidate",
        message="This extension has no active catalog entry.",
        evidence={},
    )
    native_candidates = ()
    if source == "theme":
        monkeypatch.setattr(
            design_lint_evaluation_candidates,
            "regulator_required_passive_candidates",
            lambda _observed, _map: (unknown,),
        )
    else:
        native_candidates = (unknown,)

    with pytest.raises(ValueError, match="candidates emit rules absent from the active catalog"):
        evaluate(
            "synthetic-candidate-catalog",
            coach(observed()),
            DesignLintPolicy(),
            pcb_native_drc_candidates=native_candidates,
        )
