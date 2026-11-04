"""Component-peer results expose typed finding counts for coverage assembly."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.component_peer_pin_candidate_types import (
    ComponentPeerCandidateResult,
    ComponentPeerPinFindingCounts,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


def test_component_peer_finding_counts_are_named_by_rule() -> None:
    candidate = Candidate(
        rule_id="component.peer_power_output_unconnected",
        subject="U1 pin 1",
        message="Review peer assignments",
        evidence={},
    )

    counts = ComponentPeerPinFindingCounts.from_candidates((candidate,))

    assert counts.power_output_unconnected == 1
    assert counts.for_rule("component.peer_power_output_unconnected") == 1
    assert counts.for_rule("component.peer_signal_output_unconnected") == 0


def test_component_peer_result_rejects_counts_that_disagree_with_findings() -> None:
    candidate = Candidate(
        rule_id="component.peer_power_output_unconnected",
        subject="U1 pin 1",
        message="Review peer assignments",
        evidence={},
    )

    with pytest.raises(ValueError, match="counts must match theme candidates"):
        ComponentPeerCandidateResult(
            candidates=(candidate,),
            finding_counts=ComponentPeerPinFindingCounts(),
        )
