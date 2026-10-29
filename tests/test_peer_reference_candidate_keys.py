"""Peer coverage receives typed candidate identities and rejects evidence drift."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.peer_reference_candidate_keys import (
    CanPeerBusKey,
    I2cPeerBusKey,
    PeerReferenceCandidate,
    PeerReferenceCandidateKeys,
    Rs485PeerPairKey,
    SpiPeerClockKey,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _candidates() -> tuple[PeerReferenceCandidate, ...]:
    return (
        PeerReferenceCandidate(
            rule_id="bus.i2c_peer_reference_review",
            identity=I2cPeerBusKey("I2C_SDA", "I2C_SCL"),
            subject="I2C bus",
            message="Review",
            evidence={"SDA": ("I2C_SDA",), "SCL": ("I2C_SCL",)},
        ),
        PeerReferenceCandidate(
            rule_id="bus.spi_peer_reference_review",
            identity=SpiPeerClockKey("SPI_CLK"),
            subject="SPI clock",
            message="Review",
            evidence={"SCK": ("SPI_CLK",)},
        ),
        PeerReferenceCandidate(
            rule_id="bus.can_peer_reference_review",
            identity=CanPeerBusKey("CAN_H", "CAN_L"),
            subject="CAN bus",
            message="Review",
            evidence={"CANH": ("CAN_H",), "CANL": ("CAN_L",)},
        ),
        PeerReferenceCandidate(
            rule_id="bus.rs485_peer_reference_review",
            identity=Rs485PeerPairKey("Main", "A"),
            subject="RS-485 pair",
            message="Review",
            evidence={"bus": ("Main",), "pair": ("A",)},
        ),
    )


def test_peer_candidate_keys_are_typed_and_case_normalized() -> None:
    keys = PeerReferenceCandidateKeys.from_candidates(_candidates())

    assert keys.i2c_buses == frozenset({("i2c_sda", "i2c_scl")})
    assert keys.spi_clocks == frozenset({"spi_clk"})
    assert keys.can_buses == frozenset({("can_h", "can_l")})
    assert keys.rs485_pairs == frozenset({("main", "a")})


@pytest.mark.parametrize(("index", "field"), ((0, "SDA"), (1, "SCK"), (2, "CANL"), (3, "pair")))
def test_missing_peer_identity_fails_before_coverage(index: int, field: str) -> None:
    candidate = _candidates()[index]
    evidence = dict(candidate.evidence)
    del evidence[field]

    with pytest.raises(ValueError, match=f"needs one {field} value"):
        PeerReferenceCandidateKeys.from_candidates((replace(candidate, evidence=evidence),))


def test_ambiguous_peer_identity_fails_before_coverage() -> None:
    candidate = _candidates()[0]
    with pytest.raises(ValueError, match="needs one SDA value"):
        PeerReferenceCandidateKeys.from_candidates(
            (replace(candidate, evidence={**candidate.evidence, "SDA": ("A", "B")}),)
        )


def test_untyped_peer_candidate_cannot_claim_coverage() -> None:
    source = _candidates()[0]
    untyped = Candidate(
        rule_id=source.rule_id,
        subject=source.subject,
        message=source.message,
        evidence=source.evidence,
    )

    with pytest.raises(TypeError, match="needs a typed peer identity"):
        PeerReferenceCandidateKeys.from_candidates((untyped,))


def test_internal_peer_identity_does_not_change_public_fingerprint() -> None:
    typed = _candidates()[0]
    public_candidate = Candidate(
        rule_id=typed.rule_id,
        subject=typed.subject,
        message=typed.message,
        evidence=typed.evidence,
    )

    assert fingerprint(typed) == fingerprint(public_candidate)


def test_mutated_public_evidence_cannot_disagree_with_typed_coverage() -> None:
    candidate = _candidates()[0]
    candidate.evidence["SDA"] = ("OTHER_NET",)

    with pytest.raises(ValueError, match="needs one SDA value"):
        PeerReferenceCandidateKeys.from_candidates((candidate,))
