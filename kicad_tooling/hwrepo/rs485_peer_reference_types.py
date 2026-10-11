"""Typed project context and scan records for RS-485 reference review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .rs485_models import Rs485Analysis

Rs485PeerReferenceMapState = Literal["not_configured", "pending", "not_applicable", "required"]


@dataclass(frozen=True)
class Rs485PeerReferenceContext:
    """Authored RS-485 bus map and exact source provenance for one lint run."""

    state: Rs485PeerReferenceMapState
    analysis: Rs485Analysis | None = None
    source_path: str | None = None
    source_sha256: str | None = None


@dataclass(frozen=True)
class Rs485ReferencePinAssignment:
    """One authored reference pin and its native net assignment."""

    pin: str
    net: str | None
    expected_net: str


@dataclass(frozen=True)
class Rs485PeerReferenceEndpoint:
    """One mapped endpoint on a native line pair."""

    endpoint_id: str
    reference: str
    kind: Literal["transceiver", "connector", "other"]
    line_1_pin: str
    line_2_pin: str
    line_1_net: str
    line_2_net: str
    reference_net: str | None
    reference_pins: tuple[Rs485ReferencePinAssignment, ...]
    reference_issue: str | None = None


@dataclass(frozen=True)
class Rs485PeerReferencePair:
    """Native RS-485 pair membership and endpoint reference assignments."""

    bus_id: str
    pair_id: str
    line_1_net: str
    line_2_net: str
    endpoints: tuple[Rs485PeerReferenceEndpoint, ...]
    incomplete_references: tuple[str, ...]
    disposition: Literal[
        "COMMON_REFERENCE",
        "INCOMPLETE",
        "SPLIT_REFERENCE_REVIEW",
        "PARTIAL_SPLIT_REFERENCE_REVIEW",
    ]


@dataclass(frozen=True)
class Rs485PeerReferenceScan:
    """Map-scoped native RS-485 reference evidence."""

    map_state: Rs485PeerReferenceMapState
    source_path: str | None
    source_sha256: str | None
    analysis_sha256: str | None
    recognized_endpoint_count: int
    pairs: tuple[Rs485PeerReferencePair, ...]

    @property
    def reviews(self) -> tuple[Rs485PeerReferencePair, ...]:
        return tuple(
            pair
            for pair in self.pairs
            if pair.disposition in {"SPLIT_REFERENCE_REVIEW", "PARTIAL_SPLIT_REFERENCE_REVIEW"}
        )
