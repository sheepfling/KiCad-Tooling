"""CAN and serial output-sharing findings retain exact source groups."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.can_tx_output_sharing import can_tx_output_sharing_candidates
from kicad_tooling.hwrepo.design_lint_tx_output_sharing_candidate_evidence import (
    CanTxOutputSharingEvidence,
    SerialTxOutputSharingEvidence,
    TxOutputSharingCandidate,
)
from kicad_tooling.hwrepo.serial_tx_output_sharing import serial_tx_output_sharing_candidates
from tests.design_lint_fixtures.can_tx_output_sharing import can_tx_output_netlist
from tests.serial_participant_support import serial_tx_output_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]


def test_can_candidate_retains_and_revalidates_the_current_group() -> None:
    observed = can_tx_output_netlist()
    (candidate,) = can_tx_output_sharing_candidates(observed)

    assert isinstance(candidate, TxOutputSharingCandidate)
    assert isinstance(candidate.source_evidence, CanTxOutputSharingEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.evidence["channels"] == ("CAN channel 1", "CAN channel 2")

    changed_group = replace(candidate.source_evidence.group, net="STALE_NET")
    with pytest.raises(ValueError, match="current fitted netlist"):
        replace(candidate.source_evidence, group=changed_group)


def test_serial_candidate_retains_and_revalidates_the_current_group() -> None:
    observed = serial_tx_output_netlist()
    (candidate,) = serial_tx_output_sharing_candidates(observed)

    assert isinstance(candidate, TxOutputSharingCandidate)
    assert isinstance(candidate.source_evidence, SerialTxOutputSharingEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.evidence["channels"] == ("USART1", "USART2")

    changed_group = replace(candidate.source_evidence.group, pins=("U1.9", "U2.9"))
    with pytest.raises(ValueError, match="current fitted netlist"):
        replace(candidate.source_evidence, group=changed_group)


def test_candidate_fields_must_match_the_typed_group_projection() -> None:
    candidate = can_tx_output_sharing_candidates(can_tx_output_netlist())[0]

    with pytest.raises(ValueError, match="typed source projection"):
        replace(candidate, evidence={"net": ("STALE_NET",)})
