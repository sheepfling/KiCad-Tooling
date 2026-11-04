"""I2C shared-bus findings retain their typed scan and review sources."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_i2c_peer_candidate_evidence import (
    I2cPeerReferenceCandidate,
    I2cPeerReferenceFindingEvidence,
    project_i2c_peer_reference_evidence,
)
from kicad_tooling.hwrepo.i2c_peer_reference_scan import (
    I2cPeerEndpoint,
    I2cPeerReferenceBus,
    I2cPeerReferenceScan,
)
from kicad_tooling.hwrepo.peer_reference_assignments import PeerReferencePinAssignment
from kicad_tooling.hwrepo.peer_reference_candidate_keys import (
    I2cPeerBusKey,
    PeerReferenceCandidateKeys,
)


def _scan(
    *, incomplete_reference: bool = False
) -> tuple[I2cPeerReferenceScan, I2cPeerReferenceBus]:
    endpoints: tuple[I2cPeerEndpoint, ...] = (
        I2cPeerEndpoint(
            reference="U1",
            sda_pin="U1.1",
            scl_pin="U1.2",
            sda_net="I2C_SDA",
            scl_net="I2C_SCL",
            reference_net="GND_A",
            reference_pins=(PeerReferencePinAssignment("U1.3", "GND", "passive", "GND_A"),),
        ),
        I2cPeerEndpoint(
            reference="U2",
            sda_pin="U2.1",
            scl_pin="U2.2",
            sda_net="I2C_SDA",
            scl_net="I2C_SCL",
            reference_net="GND_B",
            reference_pins=(PeerReferencePinAssignment("U2.3", "GND", "passive", "GND_B"),),
        ),
    )
    incomplete_references: tuple[str, ...] = ()
    if incomplete_reference:
        endpoints += (
            I2cPeerEndpoint(
                reference="U3",
                sda_pin="U3.1",
                scl_pin="U3.2",
                sda_net="I2C_SDA",
                scl_net="I2C_SCL",
                reference_net=None,
                reference_pins=(),
            ),
        )
        incomplete_references = ("U3",)
    bus = I2cPeerReferenceBus(
        sda_net="I2C_SDA",
        scl_net="I2C_SCL",
        endpoints=endpoints,
        incomplete_references=incomplete_references,
        disposition=(
            "PARTIAL_SPLIT_REFERENCE_REVIEW" if incomplete_reference else "SPLIT_REFERENCE_REVIEW"
        ),
    )
    return I2cPeerReferenceScan(len(endpoints), (bus,)), bus


def test_i2c_peer_projection_preserves_identity_and_assignments() -> None:
    scan, _bus = _scan()
    review = scan.reviews[0]
    source = I2cPeerReferenceFindingEvidence(scan, review)
    candidate = I2cPeerReferenceCandidate.from_source_evidence(
        source,
        subject="SDA I2C_SDA / SCL I2C_SCL: U1, U2",
        message="Review the reference policy.",
    )

    assert dict(project_i2c_peer_reference_evidence(source).evidence) == {
        "SDA": ("I2C_SDA",),
        "SCL": ("I2C_SCL",),
        "participants": ("U1", "U2"),
        "signal_pins": ("U1.1", "U1.2", "U2.1", "U2.2"),
        "reference_assignments": (
            "U1: U1.1 on I2C_SDA; U1.2 on I2C_SCL; U1.3 on GND_A",
            "U2: U2.1 on I2C_SDA; U2.2 on I2C_SCL; U2.3 on GND_B",
        ),
    }
    assert candidate.source_evidence is source
    assert candidate.identity == I2cPeerBusKey("I2C_SDA", "I2C_SCL")
    assert PeerReferenceCandidateKeys.from_candidates((candidate,)).i2c_buses == frozenset(
        {("i2c_sda", "i2c_scl")}
    )


def test_i2c_peer_projection_keeps_incomplete_reference_clues_conditional() -> None:
    scan, _bus = _scan(incomplete_reference=True)
    source = I2cPeerReferenceFindingEvidence(scan, scan.reviews[0])

    evidence = project_i2c_peer_reference_evidence(source).evidence

    assert evidence["participants"] == ("U1", "U2", "U3")
    assert evidence["incomplete_reference_evidence"] == ("U3",)
    assert evidence["reference_assignments"][-1] == (
        "U3: U3.1 on I2C_SDA; U3.2 on I2C_SCL; reference assignment incomplete"
    )


def test_i2c_peer_source_rejects_a_review_from_another_scan() -> None:
    scan, _bus = _scan()
    other_scan, _other_bus = _scan(incomplete_reference=True)

    with pytest.raises(ValueError, match="must belong to its source scan"):
        I2cPeerReferenceFindingEvidence(other_scan, scan.reviews[0])


def test_i2c_peer_candidate_rejects_a_projection_mismatch() -> None:
    scan, _bus = _scan()
    source = I2cPeerReferenceFindingEvidence(scan, scan.reviews[0])

    with pytest.raises(ValueError, match="typed source projection"):
        I2cPeerReferenceCandidate(
            rule_id="bus.i2c_peer_reference_review",
            subject="review",
            message="inspect",
            evidence={"SDA": ("I2C_SDA",), "SCL": ("I2C_SCL",), "participants": ("wrong",)},
            identity=I2cPeerBusKey("I2C_SDA", "I2C_SCL"),
            source_evidence=source,
        )
