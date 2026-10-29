"""Peer coverage receives typed candidate identities and rejects evidence drift."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.peer_reference_candidate_keys import PeerReferenceCandidateKeys

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _candidates() -> tuple[Candidate, ...]:
    return (
        Candidate(
            rule_id="bus.i2c_peer_reference_review",
            subject="I2C bus",
            message="Review",
            evidence={"SDA": ("I2C_SDA",), "SCL": ("I2C_SCL",)},
        ),
        Candidate(
            rule_id="bus.spi_peer_reference_review",
            subject="SPI clock",
            message="Review",
            evidence={"SCK": ("SPI_CLK",)},
        ),
        Candidate(
            rule_id="bus.can_peer_reference_review",
            subject="CAN bus",
            message="Review",
            evidence={"CANH": ("CAN_H",), "CANL": ("CAN_L",)},
        ),
        Candidate(
            rule_id="bus.rs485_peer_reference_review",
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
