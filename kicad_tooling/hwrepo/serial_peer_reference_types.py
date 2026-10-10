"""Typed evidence for serial peer reference-domain review."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from .models import ReferenceBondRequirement
from .serial_participants import SerialNativePeerLink


class PinNetView(Protocol):
    pin: str
    net: str


class SerialEndpointView(Protocol):
    reference: str
    symbol: str
    footprint: str
    tx: PinNetView
    rx: PinNetView
    reference_pins: tuple[PinNetView, ...]


class DirectPeerView(Protocol):
    endpoint: SerialEndpointView


class PeerLinkView(Protocol):
    endpoint: SerialEndpointView
    peer: object
    reference_policy: str
    reference_bond: ReferenceBondRequirement | None


class SerialAnalysisView(Protocol):
    links: tuple[PeerLinkView, ...]


@dataclass(frozen=True)
class SerialReferencePinAssignment:
    pin: str
    function: str
    electrical_type: str
    net: str


@dataclass(frozen=True)
class SerialReferenceDomain:
    net: str
    pins: tuple[SerialReferencePinAssignment, ...]


@dataclass(frozen=True)
class SerialPeerReferenceReview:
    first_reference: str
    second_reference: str
    first_reference_domain: SerialReferenceDomain
    second_reference_domain: SerialReferenceDomain
    links: tuple[SerialNativePeerLink, ...]
    label_links: tuple[SerialLabelPeerLink, ...] = ()


@dataclass(frozen=True)
class SerialPeerReferenceScan:
    """Reference-domain candidates with bounded peer and evidence counts."""

    reviews: tuple[SerialPeerReferenceReview, ...]
    link_entries: tuple[SerialPeerReferenceLinkCoverage, ...]
    native_peer_link_count: int
    label_peer_link_count: int
    supported_reference_link_count: int
    incomplete_reference_link_count: int
    common_reference_link_count: int
    separate_reference_link_count: int
    mapped_separate_reference_link_count: int

    @property
    def candidate_group_count(self) -> int:
        return len(self.reviews)


@dataclass(frozen=True)
class SerialPeerReferenceLinkCoverage:
    """Identity, signal evidence, and reference disposition for one discovered link."""

    discovery_basis: Literal["native_function", "channel_label"]
    first_reference: str
    second_reference: str
    signal_group: str
    signal_nets: tuple[str, ...]
    signal_pins: tuple[str, ...]
    disposition: Literal[
        "INCOMPLETE",
        "COMMON_REFERENCE",
        "SEPARATE_REFERENCE_REVIEW",
        "MAP_COVERED_SEPARATE_REFERENCE",
    ]


@dataclass(frozen=True)
class SerialLabelPeerLink:
    """Direct two-IC UART segment identified by an exact TX/RX channel label pair."""

    channel: str
    tx_net: str
    rx_net: str
    first_reference: str
    second_reference: str
    first_tx_pin: str
    second_tx_pin: str
    first_rx_pin: str
    second_rx_pin: str


@dataclass
class ReviewGroup:
    first_reference: str
    second_reference: str
    first_reference_domain: SerialReferenceDomain
    second_reference_domain: SerialReferenceDomain
    links: set[SerialNativePeerLink] = field(default_factory=set)  # pyright: ignore[reportUnknownVariableType]
    label_links: set[SerialLabelPeerLink] = field(default_factory=set)  # pyright: ignore[reportUnknownVariableType]
