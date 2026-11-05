"""Verify source-bound candidate projections for named-rail terminal order."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.component_bjt_terminal_order import (
    bjts_with_unusual_collector_emitter_rail_order,
)
from kicad_tooling.hwrepo.component_mosfet_terminal_order import (
    mosfets_with_unusual_drain_source_rail_order,
)
from kicad_tooling.hwrepo.design_lint_component_terminal_order_candidate_evidence import (
    BjtTerminalOrderEvidence,
    ComponentTerminalOrderCandidate,
    MosfetTerminalOrderEvidence,
)
from tests.design_lint_fixtures.bjt_terminal_order import bjt_terminal_order_netlist
from tests.design_lint_fixtures.mosfet_terminal_order import mosfet_terminal_order_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.evidence_lint]


@pytest.mark.parametrize("family", ("npn", "pnp"))
def test_bjt_candidate_projection_retains_current_terminal_and_rail_source(family: str) -> None:
    observed = bjt_terminal_order_netlist(family=family)
    candidate = bjts_with_unusual_collector_emitter_rail_order(observed)[0]

    assert isinstance(candidate, ComponentTerminalOrderCandidate)
    assert isinstance(candidate.source_evidence, BjtTerminalOrderEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.evidence["collector_pin"] == ("Q1.2",)
    assert candidate.evidence["emitter_pin"] == ("Q1.3",)
    assert candidate.evidence["expected_lower_terminal"] == (
        "emitter" if family == "npn" else "collector",
    )
    assert candidate.evidence["observed_lower_terminal"] == (
        "collector" if family == "npn" else "emitter",
    )

    repaired = bjt_terminal_order_netlist(family=family, reversed_order=False)
    with pytest.raises(ValueError, match="current native assignment"):
        replace(candidate.source_evidence, observed=repaired)


@pytest.mark.parametrize("channel_type", ("nmos", "pmos"))
def test_mosfet_candidate_projection_retains_current_terminal_and_rail_source(
    channel_type: str,
) -> None:
    observed = mosfet_terminal_order_netlist(channel_type=channel_type)
    candidate = mosfets_with_unusual_drain_source_rail_order(observed)[0]

    assert isinstance(candidate, ComponentTerminalOrderCandidate)
    assert isinstance(candidate.source_evidence, MosfetTerminalOrderEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.evidence["drain_pin"] == ("Q1.1",)
    assert candidate.evidence["source_pin"] == ("Q1.3",)
    assert candidate.evidence["expected_lower_terminal"] == (
        "source" if channel_type == "nmos" else "drain",
    )
    assert candidate.evidence["observed_lower_terminal"] == (
        "drain" if channel_type == "nmos" else "source",
    )

    repaired = mosfet_terminal_order_netlist(channel_type=channel_type, reversed_order=False)
    with pytest.raises(ValueError, match="current native assignment"):
        replace(candidate.source_evidence, observed=repaired)


def test_candidate_rejects_report_fields_that_do_not_match_terminal_source() -> None:
    candidate = bjts_with_unusual_collector_emitter_rail_order(bjt_terminal_order_netlist())[0]

    with pytest.raises(ValueError, match="typed projection"):
        ComponentTerminalOrderCandidate(
            rule_id=candidate.rule_id,
            subject=candidate.subject,
            message=candidate.message,
            evidence={"collector_net": ("OTHER",)},
            source_evidence=candidate.source_evidence,
        )
