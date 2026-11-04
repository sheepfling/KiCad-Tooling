"""BJT and MOSFET terminal findings retain typed native observations."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_component_candidates import component_candidates
from kicad_tooling.hwrepo.design_lint_component_terminal_candidate_evidence import (
    ComponentTerminalCandidate,
    project_component_terminal_evidence,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.bjt_collector_emitter_same_net import (
    bjt_base_collector_netlist,
    bjt_base_emitter_netlist,
    bjt_collector_emitter_netlist,
)
from tests.design_lint_fixtures.mosfet_drain_source_same_net import mosfet_drain_source_netlist
from tests.design_lint_fixtures.mosfet_terminal_same_net import mosfet_terminal_same_net_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


@pytest.mark.parametrize(
    ("rule_id", "observed"),
    [
        ("component.bjt_collector_emitter_same_net", bjt_collector_emitter_netlist()),
        ("component.bjt_base_emitter_same_net", bjt_base_emitter_netlist()),
        ("component.bjt_base_collector_same_net", bjt_base_collector_netlist()),
        ("component.mosfet_drain_source_same_net", mosfet_drain_source_netlist()),
        (
            "component.mosfet_gate_source_same_net",
            mosfet_terminal_same_net_netlist(pair="gate-source"),
        ),
        (
            "component.mosfet_gate_drain_same_net",
            mosfet_terminal_same_net_netlist(pair="gate-drain"),
        ),
    ],
    ids=["bjt-ce", "bjt-be", "bjt-bc", "mosfet-ds", "mosfet-gs", "mosfet-gd"],
)
def test_terminal_candidate_retains_source_and_keeps_public_fingerprint(
    rule_id: str,
    observed: NetlistContract,
) -> None:
    candidate = next(item for item in component_candidates(observed) if item.rule_id == rule_id)

    assert isinstance(candidate, ComponentTerminalCandidate)
    assert candidate.source_evidence.rule_id == rule_id
    assert (
        candidate.source_evidence.first_net.casefold()
        == candidate.source_evidence.second_net.casefold()
    )
    assert (
        candidate.evidence
        == project_component_terminal_evidence(candidate.source_evidence).evidence
    )
    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)
