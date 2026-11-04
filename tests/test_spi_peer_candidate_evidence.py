"""SPI shared-clock findings retain their typed scan and review sources."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_spi_peer_candidate_evidence import (
    SpiPeerReferenceCandidate,
    SpiPeerReferenceFindingEvidence,
    project_spi_peer_reference_evidence,
)
from kicad_tooling.hwrepo.peer_reference_assignments import PeerReferencePinAssignment
from kicad_tooling.hwrepo.peer_reference_candidate_keys import (
    PeerReferenceCandidateKeys,
    SpiPeerClockKey,
)
from kicad_tooling.hwrepo.spi_peer_reference_scan import (
    SpiClockEndpoint,
    SpiClockPeerBus,
    SpiPeerReferenceScan,
)


def _scan(*, incomplete_reference: bool = False) -> tuple[SpiPeerReferenceScan, SpiClockPeerBus]:
    endpoints: tuple[SpiClockEndpoint, ...] = (
        SpiClockEndpoint(
            reference="U1",
            clock_pin="U1.1",
            clock_type="output",
            clock_net="SPI_CLK",
            reference_net="GND_A",
            reference_pins=(PeerReferencePinAssignment("U1.2", "GND", "passive", "GND_A"),),
        ),
        SpiClockEndpoint(
            reference="U2",
            clock_pin="U2.1",
            clock_type="input",
            clock_net="SPI_CLK",
            reference_net="GND_B",
            reference_pins=(PeerReferencePinAssignment("U2.2", "GND", "passive", "GND_B"),),
        ),
    )
    incomplete_references: tuple[str, ...] = ()
    if incomplete_reference:
        endpoints += (
            SpiClockEndpoint(
                reference="U3",
                clock_pin="U3.1",
                clock_type="input",
                clock_net="SPI_CLK",
                reference_net=None,
                reference_pins=(),
            ),
        )
        incomplete_references = ("U3",)
    review = SpiClockPeerBus(
        clock_net="SPI_CLK",
        endpoints=endpoints,
        incomplete_references=incomplete_references,
        disposition=(
            "PARTIAL_SPLIT_REFERENCE_REVIEW" if incomplete_reference else "SPLIT_REFERENCE_REVIEW"
        ),
    )
    return SpiPeerReferenceScan(len(endpoints), (review,)), review


def test_spi_peer_projection_preserves_identity_and_review_assignments() -> None:
    scan, review = _scan()
    source = SpiPeerReferenceFindingEvidence(scan, review)
    candidate = SpiPeerReferenceCandidate.from_source_evidence(
        source,
        subject="SCK SPI_CLK: U1, U2",
        message="Review the reference policy.",
    )

    assert dict(project_spi_peer_reference_evidence(source).evidence) == {
        "SCK": ("SPI_CLK",),
        "participants": ("U1", "U2"),
        "clock_pins": ("U1.1", "U2.1"),
        "reference_assignments": (
            "U1: U1.1 on SPI_CLK; U1.2 on GND_A",
            "U2: U2.1 on SPI_CLK; U2.2 on GND_B",
        ),
    }
    assert candidate.source_evidence is source
    assert candidate.identity == SpiPeerClockKey("SPI_CLK")
    assert PeerReferenceCandidateKeys.from_candidates((candidate,)).spi_clocks == frozenset(
        {"spi_clk"}
    )


def test_spi_peer_projection_keeps_incomplete_reference_clues_conditional() -> None:
    scan, review = _scan(incomplete_reference=True)
    source = SpiPeerReferenceFindingEvidence(scan, review)

    evidence = project_spi_peer_reference_evidence(source).evidence

    assert evidence["participants"] == ("U1", "U2", "U3")
    assert evidence["incomplete_reference_evidence"] == ("U3",)
    assert evidence["reference_assignments"][-1] == (
        "U3: U3.1 on SPI_CLK; reference assignment incomplete"
    )


def test_spi_peer_source_rejects_a_review_from_another_scan() -> None:
    _source_scan, review = _scan()
    other_scan, _other_review = _scan(incomplete_reference=True)

    with pytest.raises(ValueError, match="must belong to its source scan"):
        SpiPeerReferenceFindingEvidence(other_scan, review)


def test_spi_peer_candidate_rejects_a_projection_mismatch() -> None:
    scan, review = _scan()
    source = SpiPeerReferenceFindingEvidence(scan, review)

    with pytest.raises(ValueError, match="typed source projection"):
        SpiPeerReferenceCandidate(
            rule_id="bus.spi_peer_reference_review",
            subject="review",
            message="inspect",
            evidence={"SCK": ("SPI_CLK",), "participants": ("wrong",)},
            identity=SpiPeerClockKey("SPI_CLK"),
            source_evidence=source,
        )
