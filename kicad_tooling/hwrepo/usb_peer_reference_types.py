"""Typed evidence records for bounded USB peer-reference analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class UsbReferencePinAssignment:
    pin: str
    function: str
    electrical_type: str
    net: str


@dataclass(frozen=True)
class UsbPeerDataShuntBranch:
    data_pin: str
    reference_pin: str
    symbol: str
    data_net: str
    reference_net: str


@dataclass(frozen=True)
class UsbPeerDataSeriesResistor:
    reference: str
    symbol: str
    footprint: str
    value: str
    connector_pin: str
    phy_pin: str
    connector_net: str
    phy_net: str


@dataclass(frozen=True)
class UsbPeerDataLink:
    connector_positive_pin: str
    phy_positive_pin: str
    connector_positive_net: str
    phy_positive_net: str
    connector_negative_pin: str
    phy_negative_pin: str
    connector_negative_net: str
    phy_negative_net: str
    connector_positive_pins: tuple[str, ...]
    phy_positive_pins: tuple[str, ...]
    connector_negative_pins: tuple[str, ...]
    phy_negative_pins: tuple[str, ...]
    positive_shunt_branches: tuple[UsbPeerDataShuntBranch, ...] = ()
    negative_shunt_branches: tuple[UsbPeerDataShuntBranch, ...] = ()
    positive_series_resistor: UsbPeerDataSeriesResistor | None = None
    negative_series_resistor: UsbPeerDataSeriesResistor | None = None
    port_group: str | None = None


@dataclass(frozen=True)
class UsbPeerReferenceReview:
    connector_reference: str
    phy_reference: str
    connector_symbol: str
    phy_symbol: str
    connector_footprint: str
    phy_footprint: str
    connector_reference_net: str
    phy_reference_net: str
    connector_reference_pins: tuple[UsbReferencePinAssignment, ...]
    phy_reference_pins: tuple[UsbReferencePinAssignment, ...]
    data_link: UsbPeerDataLink


@dataclass(frozen=True)
class UsbPeerReferencePathCoverage:
    """One supported connector-to-PHY path and its reference disposition."""

    connector_reference: str
    phy_reference: str
    connector_symbol: str
    phy_symbol: str
    connector_footprint: str
    phy_footprint: str
    connector_reference_net: str
    phy_reference_net: str
    connector_reference_pins: tuple[UsbReferencePinAssignment, ...]
    phy_reference_pins: tuple[UsbReferencePinAssignment, ...]
    reference_disposition: Literal[
        "COMMON_REFERENCE",
        "SEPARATE_REFERENCE_REVIEW",
        "MAP_COVERED_SEPARATE_REFERENCE",
    ]
    data_link: UsbPeerDataLink


@dataclass(frozen=True)
class UsbPeerReferenceCoverage:
    """Bounded endpoint and data-path counts for the USB reference heuristic."""

    endpoint_groups: tuple[UsbPeerEndpointGroupCoverage, ...]
    path_entries: tuple[UsbPeerReferencePathCoverage, ...]
    recognized_connector_group_count: int
    supported_connector_group_count: int
    recognized_phy_group_count: int
    supported_phy_group_count: int
    dnp_group_count: int
    incomplete_group_count: int
    supported_data_path_count: int
    common_reference_path_count: int
    separate_reference_path_count: int
    mapped_separate_reference_path_count: int
    review_candidate_group_count: int


@dataclass(frozen=True)
class UsbPeerEndpointGroupCoverage:
    """Identity and bounded disposition for one recognized USB endpoint group."""

    endpoint_role: Literal["connector", "phy"]
    reference: str
    port_group: str | None
    disposition: Literal["SUPPORTED", "INCOMPLETE", "DNP"]


@dataclass(frozen=True)
class UsbPeerReferenceScan:
    """Review candidates and applicability counts from one deterministic scan."""

    reviews: tuple[UsbPeerReferenceReview, ...]
    coverage: UsbPeerReferenceCoverage


@dataclass(frozen=True)
class UsbEndpoint:
    reference: str
    symbol: str
    footprint: str
    positive_pins: tuple[str, ...]
    positive_net: str
    negative_pins: tuple[str, ...]
    negative_net: str
    reference_net: str
    reference_pins: tuple[UsbReferencePinAssignment, ...]
    port_group: str | None
