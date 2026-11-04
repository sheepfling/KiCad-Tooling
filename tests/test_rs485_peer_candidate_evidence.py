"""Mapped RS-485 findings retain their typed source scan and pair."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_rs485_peer_candidate_evidence import (
    Rs485PeerReferenceCandidate,
    Rs485PeerReferenceFindingEvidence,
    project_rs485_peer_reference_evidence,
)
from kicad_tooling.hwrepo.peer_reference_candidate_keys import (
    PeerReferenceCandidateKeys,
    Rs485PeerPairKey,
)
from kicad_tooling.hwrepo.rs485_peer_reference_types import (
    Rs485PeerReferenceEndpoint,
    Rs485PeerReferencePair,
    Rs485PeerReferenceScan,
    Rs485ReferencePinAssignment,
)


def _scan(
    *, incomplete_reference: bool = False
) -> tuple[Rs485PeerReferenceScan, Rs485PeerReferencePair]:
    endpoints: tuple[Rs485PeerReferenceEndpoint, ...] = (
        Rs485PeerReferenceEndpoint(
            endpoint_id="endpoint-u1",
            reference="U1",
            kind="transceiver",
            line_1_pin="U1.1",
            line_2_pin="U1.2",
            line_1_net="RS485_A",
            line_2_net="RS485_B",
            reference_net="GND_A",
            reference_pins=(Rs485ReferencePinAssignment("U1.5", "GND_A", "GND_A"),),
        ),
        Rs485PeerReferenceEndpoint(
            endpoint_id="endpoint-u2",
            reference="U2",
            kind="transceiver",
            line_1_pin="U2.1",
            line_2_pin="U2.2",
            line_1_net="RS485_A",
            line_2_net="RS485_B",
            reference_net="GND_B",
            reference_pins=(Rs485ReferencePinAssignment("U2.5", "GND_B", "GND_B"),),
        ),
    )
    incomplete_references: tuple[str, ...] = ()
    if incomplete_reference:
        endpoints += (
            Rs485PeerReferenceEndpoint(
                endpoint_id="endpoint-u3",
                reference="U3",
                kind="transceiver",
                line_1_pin="U3.1",
                line_2_pin="U3.2",
                line_1_net="RS485_A",
                line_2_net="RS485_B",
                reference_net=None,
                reference_pins=(Rs485ReferencePinAssignment("U3.5", None, "GND_C"),),
            ),
        )
        incomplete_references = ("U3",)
    pair = Rs485PeerReferencePair(
        bus_id="field-bus",
        pair_id="pair-a",
        line_1_net="RS485_A",
        line_2_net="RS485_B",
        endpoints=endpoints,
        incomplete_references=incomplete_references,
        disposition=(
            "PARTIAL_SPLIT_REFERENCE_REVIEW" if incomplete_reference else "SPLIT_REFERENCE_REVIEW"
        ),
    )
    scan = Rs485PeerReferenceScan(
        map_state="required",
        source_path="contracts/electrical.json",
        source_sha256="a" * 64,
        analysis_sha256="b" * 64,
        recognized_endpoint_count=len(endpoints),
        pairs=(pair,),
    )
    return scan, pair


def test_rs485_peer_projection_preserves_identity_and_authored_map_source() -> None:
    scan, pair = _scan()
    source = Rs485PeerReferenceFindingEvidence(scan, pair)
    candidate = Rs485PeerReferenceCandidate.from_source_evidence(
        source,
        subject="RS-485 bus field-bus pair pair-a: U1, U2",
        message="Review the mapped reference policy.",
    )

    assert dict(project_rs485_peer_reference_evidence(source).evidence) == {
        "bus": ("field-bus",),
        "pair": ("pair-a",),
        "line_1": ("RS485_A",),
        "line_2": ("RS485_B",),
        "participants": ("U1", "U2"),
        "reference_assignments": ("U1: U1.5 on GND_A", "U2: U2.5 on GND_B"),
        "reference_nets": ("GND_A", "GND_B"),
    }
    assert candidate.source_evidence is source
    assert candidate.source_evidence.scan.source_path == "contracts/electrical.json"
    assert candidate.source_evidence.scan.source_sha256 == "a" * 64
    assert candidate.identity == Rs485PeerPairKey("field-bus", "pair-a")
    assert PeerReferenceCandidateKeys.from_candidates((candidate,)).rs485_pairs == frozenset(
        {("field-bus", "pair-a")}
    )


def test_rs485_peer_projection_keeps_incomplete_reference_clues_conditional() -> None:
    scan, pair = _scan(incomplete_reference=True)
    source = Rs485PeerReferenceFindingEvidence(scan, pair)

    evidence = project_rs485_peer_reference_evidence(source).evidence

    assert evidence["participants"] == ("U1", "U2", "U3")
    assert evidence["reference_assignments"][-1] == "U3: U3.5 on unassigned"
    assert evidence["reference_nets"] == ("GND_A", "GND_B")
    assert evidence["incomplete_reference_evidence"] == ("U3",)


def test_rs485_peer_source_rejects_a_pair_from_another_scan() -> None:
    _source_scan, pair = _scan()
    other_scan, _other_pair = _scan(incomplete_reference=True)

    with pytest.raises(ValueError, match="must belong to its source scan"):
        Rs485PeerReferenceFindingEvidence(other_scan, pair)


def test_rs485_peer_candidate_rejects_a_projection_mismatch() -> None:
    scan, pair = _scan()
    source = Rs485PeerReferenceFindingEvidence(scan, pair)

    with pytest.raises(ValueError, match="typed source projection"):
        Rs485PeerReferenceCandidate(
            rule_id="bus.rs485_peer_reference_review",
            subject="review",
            message="inspect",
            evidence={"bus": ("field-bus",), "pair": ("pair-a",), "participants": ("wrong",)},
            identity=Rs485PeerPairKey("field-bus", "pair-a"),
            source_evidence=source,
        )
