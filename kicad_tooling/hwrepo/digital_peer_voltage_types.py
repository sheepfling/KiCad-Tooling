"""Typed records for source-bound digital peer voltage review."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Literal

from .digital_peer_voltage_models import DigitalPeerVoltageAnalysis


@dataclass(frozen=True, slots=True)
class DigitalPeerVoltageLintContext:
    """Project contract state and provenance for digital-peer voltage reviews."""

    state: Literal["not_configured", "pending", "not_applicable", "required"]
    analysis: DigitalPeerVoltageAnalysis | None = None
    source_path: str | None = None
    source_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class DigitalPeerPinAssignmentIndex:
    """Named native pin, component-reference, and symbol indexes for one netlist."""

    net_names_by_pin_key: Mapping[str, frozenset[str]]
    canonical_references_by_key: Mapping[str, str]
    symbols_by_reference_key: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "net_names_by_pin_key",
            MappingProxyType(
                {key: frozenset(names) for key, names in self.net_names_by_pin_key.items()}
            ),
        )
        object.__setattr__(
            self,
            "canonical_references_by_key",
            MappingProxyType(dict(self.canonical_references_by_key)),
        )
        object.__setattr__(
            self,
            "symbols_by_reference_key",
            MappingProxyType(dict(self.symbols_by_reference_key)),
        )


@dataclass(frozen=True, slots=True)
class VoltageNamedRail:
    net: str
    voltage_v: Decimal


@dataclass(frozen=True, slots=True)
class DigitalPeerLink:
    interface: Literal["SPI", "serial"]
    output_role: str | None
    output_reference: str
    output_pin: str
    output_function: str
    output_type: str
    input_reference: str
    input_role: str | None
    input_pin: str
    input_function: str
    input_type: str
    net: str


@dataclass(frozen=True, slots=True)
class DigitalPeerVoltageReview:
    interface: Literal["SPI", "serial"]
    output_reference: str
    input_reference: str
    output_rail: VoltageNamedRail
    input_rail: VoltageNamedRail
    links: tuple[DigitalPeerLink, ...]


@dataclass(frozen=True, slots=True)
class DigitalPeerVoltageCoverage:
    """Counts the supported direct-peer links examined by one interface rule."""

    interface: Literal["SPI", "serial"]
    recognized_endpoint_count: int
    assigned_endpoint_count: int
    direct_peer_link_count: int
    voltage_comparison_count: int
    same_voltage_link_count: int
    different_voltage_link_count: int
    mapped_mismatch_link_count: int
    review_candidate_group_count: int


@dataclass(frozen=True, slots=True)
class DigitalPeerVoltageScan:
    """Grouped review candidates plus bounded applicability counts."""

    reviews: tuple[DigitalPeerVoltageReview, ...]
    coverage: tuple[DigitalPeerVoltageCoverage, ...]
