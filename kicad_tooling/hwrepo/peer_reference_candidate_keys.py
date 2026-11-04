"""Typed peer identities carried from rule owners into coverage assembly."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from .design_lint_rule_types import DesignLintRuleId
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


@dataclass(frozen=True, slots=True)
class PeerReferenceIdentityProjection:
    """Project a typed peer identity into its stable finding rule and wire fields."""

    rule_id: DesignLintRuleId
    evidence: Mapping[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))


def _identity_projection(identity: PeerReferenceKey) -> PeerReferenceIdentityProjection:
    if isinstance(identity, I2cPeerBusKey):
        return PeerReferenceIdentityProjection(
            rule_id="bus.i2c_peer_reference_review",
            evidence={"SDA": (identity.sda_net,), "SCL": (identity.scl_net,)},
        )
    if isinstance(identity, SpiPeerClockKey):
        return PeerReferenceIdentityProjection(
            rule_id="bus.spi_peer_reference_review",
            evidence={"SCK": (identity.clock_net,)},
        )
    if isinstance(identity, CanPeerBusKey):
        return PeerReferenceIdentityProjection(
            rule_id="bus.can_peer_reference_review",
            evidence={"CANH": (identity.canh_net,), "CANL": (identity.canl_net,)},
        )
    return PeerReferenceIdentityProjection(
        rule_id="bus.rs485_peer_reference_review",
        evidence={"bus": (identity.bus_id,), "pair": (identity.pair_id,)},
    )


@dataclass(frozen=True, slots=True)
class PeerReferenceCandidate(Candidate):
    """Keep the internal coverage key bound to its serialized finding evidence."""

    identity: PeerReferenceKey

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        self.validate_identity_contract()

    @classmethod
    def from_identity(
        cls,
        *,
        identity: PeerReferenceKey,
        subject: str,
        message: str,
        evidence: Mapping[str, tuple[str, ...]],
    ) -> PeerReferenceCandidate:
        """Serialize identity-owned fields from the typed key into legacy evidence."""
        projection = _identity_projection(identity)
        duplicated = projection.evidence.keys() & evidence.keys()
        if duplicated:
            names = ", ".join(sorted(duplicated))
            raise ValueError(f"Peer evidence fields are supplied by identity: {names}")
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence={**projection.evidence, **evidence},
            identity=identity,
        )

    def validate_identity_contract(self) -> None:
        """Check identity-owned evidence against its source-derived projection."""
        projection = _identity_projection(self.identity)
        if self.rule_id != projection.rule_id:
            raise ValueError(
                f"{self.rule_id} does not match peer identity for {projection.rule_id}"
            )
        for field, values in projection.evidence.items():
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

    def merge(self, other: PeerReferenceCandidateKeys) -> PeerReferenceCandidateKeys:
        """Combine typed peer identities returned by independent theme owners."""
        return PeerReferenceCandidateKeys(
            i2c_buses=self.i2c_buses | other.i2c_buses,
            spi_clocks=self.spi_clocks | other.spi_clocks,
            can_buses=self.can_buses | other.can_buses,
            rs485_pairs=self.rs485_pairs | other.rs485_pairs,
        )
