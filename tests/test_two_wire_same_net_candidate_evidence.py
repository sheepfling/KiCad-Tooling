"""I2C and I3C same-net findings retain source-bound pin-role pairs."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint_two_wire_same_net_candidate_evidence import (
    I2cSameNetEvidence,
    I3cSameNetEvidence,
    TwoWireSameNetCandidate,
)
from kicad_tooling.hwrepo.i2c_same_net import i2c_sda_scl_same_net_candidates
from kicad_tooling.hwrepo.i3c_same_net import i3c_sda_scl_same_net_candidates
from tests.design_lint_fixtures.i2c_signal_label import i2c_signal_same_net_netlist
from tests.design_lint_fixtures.i3c_same_net import i3c_same_net_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]


def test_i2c_candidate_retains_source_and_rejects_a_changed_assignment() -> None:
    observed = i2c_signal_same_net_netlist()
    (candidate,) = i2c_sda_scl_same_net_candidates(observed)

    assert isinstance(candidate, TwoWireSameNetCandidate)
    assert isinstance(candidate.source_evidence, I2cSameNetEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.evidence["SDA_pin"] == ("U1.1",)

    with pytest.raises(ValueError, match="exact current assignments"):
        replace(candidate.source_evidence, net="STALE_NET")


def test_i3c_candidate_retains_channel_and_rejects_a_changed_role_pair() -> None:
    observed = i3c_same_net_netlist()
    (candidate,) = i3c_sda_scl_same_net_candidates(observed)

    assert isinstance(candidate, TwoWireSameNetCandidate)
    assert isinstance(candidate.source_evidence, I3cSameNetEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.evidence["channel"] == ("1",)

    with pytest.raises(ValueError, match="one current SDA/SCL pair"):
        replace(candidate.source_evidence, channel="2")


def test_candidate_wire_fields_must_match_the_source_projection() -> None:
    candidate = i2c_sda_scl_same_net_candidates(i2c_signal_same_net_netlist())[0]

    with pytest.raises(ValueError, match="typed source projection"):
        replace(candidate, evidence={"net": ("STALE_NET",)})
