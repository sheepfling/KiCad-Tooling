"""Generic component-peer findings retain typed, immutable scan evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.component_peer_pin_evaluation import (
    component_peer_pin_assignment_scans,
)
from kicad_tooling.hwrepo.component_peer_pin_scan import PeerPinAssignmentOutlier
from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_component_peer_candidate_evidence import (
    GenericPeerPinCandidate,
)
from kicad_tooling.hwrepo.design_lint_component_peer_candidates import (
    component_peer_candidates,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from tests.component_peer_pin_support import peer_component_pin_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


def test_generic_peer_finding_retains_its_scan_record_and_public_projection() -> None:
    observed = peer_component_pin_netlist(
        references=("U1", "U2", "U3"),
        pin_nets=("PEER_DATA", "PEER_DATA", "OTHER_DATA"),
        default_symbol="Synthetic:PeerModule",
        pin_electrical_types=("passive", "passive", "passive"),
        pin_function="Pin_2",
    )
    scans = component_peer_pin_assignment_scans(observed)
    candidate = next(
        item
        for item in component_peer_candidates(observed, peer_pin_scans=scans)
        if item.rule_id == "component.generic_peer_pin_assignment_outlier"
    )

    assert isinstance(candidate, GenericPeerPinCandidate)
    assert candidate.source_evidence == scans.generic_assignment_outlier.outliers[0]
    assert candidate.evidence == {
        "U1.2": ("PEER_DATA",),
        "U2.2": ("PEER_DATA",),
        "U3.2": ("OTHER_DATA",),
        "peer_group_basis": ("exact_symbol",),
        "peer_group_identity": ("Synthetic:PeerModule",),
        "peer_group_symbols": ("Synthetic:PeerModule",),
        "symbol": ("Synthetic:PeerModule",),
        "pin_number": ("2",),
        "pin_function": ("Pin_2",),
        "pin_electrical_type": ("passive",),
        "majority_net": ("PEER_DATA",),
        "outlier_pins": ("U3.2",),
        "shared_anchor_contacts": ("U1.1 / U2.1 / U3.1 -> DATA",),
    }
    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)


def test_peer_scan_record_copies_and_freezes_assignments() -> None:
    assignments = {"U1.2": ("NET_A",), "U2.2": ("NET_B",)}
    source = PeerPinAssignmentOutlier(
        symbol="Synthetic:PeerModule",
        pin_number="2",
        electrical_type="passive",
        assignments=assignments,
        peer_identity_basis="exact_symbol",
        peer_identity="Synthetic:PeerModule",
        peer_symbols=("Synthetic:PeerModule",),
        shared_anchor_contacts=("U1.1 / U2.1 -> DATA",),
        majority_net="NET_A",
        outlier_pins=("U2.2",),
    )
    assignments["U1.2"] = ("CHANGED",)

    assert source.assignments["U1.2"] == ("NET_A",)
    with pytest.raises(TypeError):
        source.assignments["U1.2"] = ("CHANGED",)  # type: ignore[index]


def test_generic_peer_candidate_rejects_evidence_that_drifted_from_source() -> None:
    source = PeerPinAssignmentOutlier(
        symbol="Synthetic:PeerModule",
        pin_number="2",
        electrical_type="passive",
        assignments={"U1.2": ("NET_A",), "U2.2": ("NET_B",)},
        peer_identity_basis="exact_symbol",
        peer_identity="Synthetic:PeerModule",
        peer_symbols=("Synthetic:PeerModule",),
        shared_anchor_contacts=("U1.1 / U2.1 -> DATA",),
        majority_net="NET_A",
        outlier_pins=("U2.2",),
    )
    candidate = GenericPeerPinCandidate.from_source_evidence(
        source,
        subject="synthetic subject",
        message="synthetic review",
    )

    with pytest.raises(ValueError, match="typed source projection"):
        replace(candidate, evidence={"majority_net": ("OTHER",)})
