"""CAN TX/RX findings retain their current native role-pair evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.can_tx_rx_same_net import can_tx_rx_same_net_candidates
from kicad_tooling.hwrepo.design_lint_can_tx_rx_candidate_evidence import (
    CanTxRxSameNetCandidate,
    CanTxRxSameNetEvidence,
)
from tests.design_lint_fixtures.can_tx_rx_same_net import can_tx_rx_same_net_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]


def test_candidate_retains_exact_can_role_pair_and_rejects_a_stale_net() -> None:
    observed = can_tx_rx_same_net_netlist()
    (candidate,) = can_tx_rx_same_net_candidates(observed)

    assert isinstance(candidate, CanTxRxSameNetCandidate)
    assert isinstance(candidate.source_evidence, CanTxRxSameNetEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.evidence == {
        "component": ("U1",),
        "channel": ("CAN channel 1",),
        "tx_pin": ("U1.1",),
        "tx_function": ("CAN1_TX",),
        "tx_electrical_type": ("output",),
        "rx_pin": ("U1.2",),
        "rx_function": ("CAN1_RX",),
        "rx_electrical_type": ("input",),
        "net": ("CAN_CONTROL_SHARED",),
    }

    with pytest.raises(ValueError, match="unique native assignments"):
        replace(candidate.source_evidence, net="STALE_NET")


def test_candidate_report_fields_must_match_the_source_projection() -> None:
    (candidate,) = can_tx_rx_same_net_candidates(can_tx_rx_same_net_netlist())

    with pytest.raises(ValueError, match="typed source projection"):
        replace(candidate, evidence={"net": ("STALE_NET",)})
