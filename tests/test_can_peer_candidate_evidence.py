"""CAN peer candidates retain their typed divergence records."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.can_peer_heuristics import can_peer_assignment_divergences
from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_can_candidates import can_candidates
from kicad_tooling.hwrepo.design_lint_can_peer_candidate_evidence import CanPeerCandidate
from kicad_tooling.hwrepo.design_lint_types import Candidate
from tests.design_lint_fixtures import can_peer_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_can_peer_candidate_retains_the_divergence_record_and_public_fingerprint() -> None:
    observed = can_peer_netlist(divergent_peer=True)
    candidate = next(
        item
        for item in can_candidates(observed)
        if item.rule_id == "bus.can_peer_assignment_divergence"
    )
    assert isinstance(candidate, CanPeerCandidate)
    assert candidate.source_evidence == can_peer_assignment_divergences(observed)[0]
    assert candidate.evidence == {
        "shared_role": ("CANH",),
        "shared_net": ("NET_A",),
        "complementary_role": ("CANL",),
        "complementary_nets": ("NET_B", "NET_C"),
        "participants": (
            "U1:U1.1=CANH/NET_A;U1.2=CANL/NET_B",
            "U2:U2.1=CANH/NET_A;U2.2=CANL/NET_B",
            "U3:U3.1=CANH/NET_A;U3.2=CANL/NET_C",
        ),
    }
    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)
