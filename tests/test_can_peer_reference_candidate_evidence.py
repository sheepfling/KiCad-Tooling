"""CAN peer-reference findings retain their typed scan and bus sources."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.can_peer_reference_scan import (
    CanPeerReferenceBus,
    CanPeerReferenceEndpoint,
    CanPeerReferenceScan,
)
from kicad_tooling.hwrepo.design_lint_can_peer_reference_candidate_evidence import (
    CanPeerReferenceCandidate,
    CanPeerReferenceFindingEvidence,
    project_can_peer_reference_evidence,
)
from kicad_tooling.hwrepo.peer_reference_assignments import PeerReferencePinAssignment
from kicad_tooling.hwrepo.peer_reference_candidate_keys import (
    CanPeerBusKey,
    PeerReferenceCandidateKeys,
)


def _scan(
    *, incomplete_reference: bool = False
) -> tuple[CanPeerReferenceScan, CanPeerReferenceBus]:
    endpoints: tuple[CanPeerReferenceEndpoint, ...] = (
        CanPeerReferenceEndpoint(
            reference="U1",
            canh_pin="U1.1",
            canh_net="CAN_H",
            canl_pin="U1.2",
            canl_net="CAN_L",
            reference_net="GND_A",
            reference_pins=(PeerReferencePinAssignment("U1.3", "GND", "passive", "GND_A"),),
        ),
        CanPeerReferenceEndpoint(
            reference="U2",
            canh_pin="U2.1",
            canh_net="CAN_H",
            canl_pin="U2.2",
            canl_net="CAN_L",
            reference_net="GND_B",
            reference_pins=(PeerReferencePinAssignment("U2.3", "GND", "passive", "GND_B"),),
        ),
    )
    incomplete_references: tuple[str, ...] = ()
    if incomplete_reference:
        endpoints += (
            CanPeerReferenceEndpoint(
                reference="U3",
                canh_pin="U3.1",
                canh_net="CAN_H",
                canl_pin="U3.2",
                canl_net="CAN_L",
                reference_net=None,
                reference_pins=(),
            ),
        )
        incomplete_references = ("U3",)
    bus = CanPeerReferenceBus(
        canh_net="CAN_H",
        canl_net="CAN_L",
        endpoints=endpoints,
        incomplete_references=incomplete_references,
        disposition=(
            "PARTIAL_SPLIT_REFERENCE_REVIEW" if incomplete_reference else "SPLIT_REFERENCE_REVIEW"
        ),
    )
    return CanPeerReferenceScan(len(endpoints), (bus,)), bus


def test_can_peer_projection_preserves_identity_and_bus_assignments() -> None:
    scan, review = _scan()
    source = CanPeerReferenceFindingEvidence(scan, review)
    candidate = CanPeerReferenceCandidate.from_source_evidence(
        source,
        subject="CANH CAN_H / CANL CAN_L: U1, U2",
        message="Review the reference policy.",
    )

    assert dict(project_can_peer_reference_evidence(source).evidence) == {
        "CANH": ("CAN_H",),
        "CANL": ("CAN_L",),
        "participants": ("U1", "U2"),
        "line_assignments": (
            "U1: U1.1 on CAN_H; U1.2 on CAN_L",
            "U2: U2.1 on CAN_H; U2.2 on CAN_L",
        ),
        "reference_assignments": (
            "U1: U1.3 on GND_A",
            "U2: U2.3 on GND_B",
        ),
    }
    assert candidate.source_evidence is source
    assert candidate.identity == CanPeerBusKey("CAN_H", "CAN_L")
    assert PeerReferenceCandidateKeys.from_candidates((candidate,)).can_buses == frozenset(
        {("can_h", "can_l")}
    )


def test_can_peer_projection_keeps_incomplete_reference_clues_conditional() -> None:
    scan, review = _scan(incomplete_reference=True)
    source = CanPeerReferenceFindingEvidence(scan, review)

    evidence = project_can_peer_reference_evidence(source).evidence

    assert evidence["participants"] == ("U1", "U2", "U3")
    assert evidence["incomplete_reference_evidence"] == ("U3",)
    assert evidence["reference_assignments"][-1] == ("U3: reference assignment incomplete")


def test_can_peer_source_rejects_a_review_from_another_scan() -> None:
    _source_scan, review = _scan()
    other_scan, _other_review = _scan(incomplete_reference=True)

    with pytest.raises(ValueError, match="must belong to its source scan"):
        CanPeerReferenceFindingEvidence(other_scan, review)


def test_can_peer_candidate_rejects_a_projection_mismatch() -> None:
    scan, review = _scan()
    source = CanPeerReferenceFindingEvidence(scan, review)

    with pytest.raises(ValueError, match="typed source projection"):
        CanPeerReferenceCandidate(
            rule_id="bus.can_peer_reference_review",
            subject="review",
            message="inspect",
            evidence={"CANH": ("CAN_H",), "CANL": ("CAN_L",), "participants": ("wrong",)},
            identity=CanPeerBusKey("CAN_H", "CAN_L"),
            source_evidence=source,
        )
