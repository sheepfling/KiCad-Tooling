"""Typed peer identities carried from rule owners into coverage assembly."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .design_lint_types import Candidate


@dataclass(frozen=True, slots=True)
class I2cPeerBusKey:
    sda_net: str
    scl_net: str


@dataclass(frozen=True, slots=True)
class SpiPeerClockKey:
    clock_net: str


@dataclass(frozen=True, slots=True)
class CanPeerBusKey:
    canh_net: str
    canl_net: str


@dataclass(frozen=True, slots=True)
class Rs485PeerPairKey:
    bus_id: str
    pair_id: str


PeerReferenceKey = I2cPeerBusKey | SpiPeerClockKey | CanPeerBusKey | Rs485PeerPairKey


def _identity_contract(identity: PeerReferenceKey) -> tuple[str, dict[str, tuple[str, ...]]]:
    if isinstance(identity, I2cPeerBusKey):
        return "bus.i2c_peer_reference_review", {
            "SDA": (identity.sda_net,),
            "SCL": (identity.scl_net,),
        }
    if isinstance(identity, SpiPeerClockKey):
        return "bus.spi_peer_reference_review", {"SCK": (identity.clock_net,)}
    if isinstance(identity, CanPeerBusKey):
        return "bus.can_peer_reference_review", {
            "CANH": (identity.canh_net,),
            "CANL": (identity.canl_net,),
        }
    return "bus.rs485_peer_reference_review", {
        "bus": (identity.bus_id,),
        "pair": (identity.pair_id,),
    }


@dataclass(frozen=True, slots=True)
class PeerReferenceCandidate(Candidate):
    """Keep the internal coverage key bound to its serialized finding evidence."""

    identity: PeerReferenceKey

    def __post_init__(self) -> None:
        self.validate_identity_contract()

    def validate_identity_contract(self) -> None:
        """Catch mutable evidence drifting from the source-derived identity."""
        rule_id, expected = _identity_contract(self.identity)
        if self.rule_id != rule_id:
            raise ValueError(f"{self.rule_id} does not match peer identity for {rule_id}")
        for field, values in expected.items():
            if not values[0] or self.evidence.get(field) != values:
                raise ValueError(
                    f"{self.rule_id} candidate for {self.subject!r} needs one {field} value"
                )


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
        peer_rule_ids = {
            "bus.i2c_peer_reference_review",
            "bus.spi_peer_reference_review",
            "bus.can_peer_reference_review",
            "bus.rs485_peer_reference_review",
        }
        for item in items:
            if item.rule_id not in peer_rule_ids:
                continue
            if not isinstance(item, PeerReferenceCandidate):
                raise TypeError(f"{item.rule_id} candidate needs a typed peer identity")
            item.validate_identity_contract()
            identity = item.identity
            if isinstance(identity, I2cPeerBusKey):
                i2c.add((identity.sda_net.casefold(), identity.scl_net.casefold()))
            elif isinstance(identity, SpiPeerClockKey):
                spi.add(identity.clock_net.casefold())
            elif isinstance(identity, CanPeerBusKey):
                can.add((identity.canh_net.casefold(), identity.canl_net.casefold()))
            else:
                rs485.add((identity.bus_id.casefold(), identity.pair_id.casefold()))
        return cls(frozenset(i2c), frozenset(spi), frozenset(can), frozenset(rs485))
