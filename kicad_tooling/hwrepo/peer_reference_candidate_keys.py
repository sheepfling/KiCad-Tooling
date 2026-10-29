"""Typed peer-reference identities recovered at the candidate/report boundary."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .design_lint_types import Candidate


def _single_identity(candidate: Candidate, field: str) -> str:
    """Require the exact one-value evidence shape emitted by a peer rule owner."""
    values = candidate.evidence.get(field)
    if values is None or len(values) != 1 or not values[0]:
        raise ValueError(
            f"{candidate.rule_id} candidate for {candidate.subject!r} needs one {field} value"
        )
    return values[0].casefold()


@dataclass(frozen=True, slots=True)
class PeerReferenceCandidateKeys:
    """Candidate identities used to reconcile four peer coverage reports."""

    i2c_buses: frozenset[tuple[str, str]]
    spi_clocks: frozenset[str]
    can_buses: frozenset[tuple[str, str]]
    rs485_pairs: frozenset[tuple[str, str]]

    @classmethod
    def from_candidates(cls, items: Sequence[Candidate]) -> PeerReferenceCandidateKeys:
        i2c: set[tuple[str, str]] = set()
        spi: set[str] = set()
        can: set[tuple[str, str]] = set()
        rs485: set[tuple[str, str]] = set()
        for item in items:
            if item.rule_id == "bus.i2c_peer_reference_review":
                i2c.add((_single_identity(item, "SDA"), _single_identity(item, "SCL")))
            elif item.rule_id == "bus.spi_peer_reference_review":
                spi.add(_single_identity(item, "SCK"))
            elif item.rule_id == "bus.can_peer_reference_review":
                can.add((_single_identity(item, "CANH"), _single_identity(item, "CANL")))
            elif item.rule_id == "bus.rs485_peer_reference_review":
                rs485.add((_single_identity(item, "bus"), _single_identity(item, "pair")))
        return cls(frozenset(i2c), frozenset(spi), frozenset(can), frozenset(rs485))
