"""Ethernet open-pair findings retain their current native source contract."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.bus_ethernet_unconnected_data import (
    ethernet_data_unconnected_pin_candidates,
)
from kicad_tooling.hwrepo.bus_ethernet_unconnected_management import (
    ethernet_management_unconnected_pin_candidates,
)
from kicad_tooling.hwrepo.design_lint_ethernet_unconnected_candidate_evidence import (
    EthernetDataOpenPairEvidence,
    EthernetManagementOpenPairEvidence,
    EthernetUnconnectedCandidate,
)
from tests.design_lint_fixtures.ethernet_data_unconnected import (
    ethernet_data_unconnected_netlist,
)
from tests.design_lint_fixtures.ethernet_management_labels import ethernet_management_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]


def test_data_pair_candidate_retains_netlist_and_rejects_changed_peer_assignment() -> None:
    observed = ethernet_data_unconnected_netlist(open_pins=("U1.1",))
    (candidate,) = ethernet_data_unconnected_pin_candidates(observed)

    assert isinstance(candidate, EthernetUnconnectedCandidate)
    assert isinstance(candidate.source_evidence, EthernetDataOpenPairEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.evidence["U1.1"] == ()
    assert candidate.evidence["ethernet_direction"] == ("TX",)
    assert candidate.evidence["ethernet_polarity"] == ("positive",)
    assert candidate.evidence["component_pin_inventory"] == ("1", "2", "3", "4")

    with pytest.raises(ValueError, match="current unique assignment"):
        replace(candidate.source_evidence, paired_net="STALE_NET")


def test_management_pair_candidate_retains_netlist_and_rejects_changed_role() -> None:
    observed = ethernet_management_netlist(open_functions=("MDC",))
    (candidate,) = ethernet_management_unconnected_pin_candidates(observed)

    assert isinstance(candidate, EthernetUnconnectedCandidate)
    assert isinstance(candidate.source_evidence, EthernetManagementOpenPairEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.evidence["ethernet_management_role"] == ("clock",)
    assert candidate.evidence["component_pin_inventory"] == ("5", "6")

    with pytest.raises(ValueError, match="MDC/MDIO role pair"):
        replace(candidate.source_evidence, open_role="data")


def test_candidate_report_fields_must_match_the_source_projection() -> None:
    observed = ethernet_data_unconnected_netlist(open_pins=("U1.1",))
    (candidate,) = ethernet_data_unconnected_pin_candidates(observed)

    with pytest.raises(ValueError, match="typed source projection"):
        replace(candidate, evidence={"U1.1": (), "paired_net": ("STALE_NET",)})
