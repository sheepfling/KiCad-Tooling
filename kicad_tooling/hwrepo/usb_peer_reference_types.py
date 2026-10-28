"""Typed evidence records for bounded USB peer-reference analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

UsbPeerSignalFamily = Literal[
    "USB 2.0 data",
    "USB SuperSpeed TX",
    "USB SuperSpeed RX",
]


@dataclass(frozen=True, slots=True)
class UsbReferencePinAssignment:
    pin: str
    function: str
    electrical_type: str
    net: str


@dataclass(frozen=True, slots=True)
class UsbPeerReferenceComponentPin:
    pin: str
    net: str
    function: str | None
    electrical_type: str | None


@dataclass(frozen=True, slots=True)
class UsbPeerReferenceComponentObservation:
    reference: str
    symbol: str | None
    value: str | None
    footprint: str | None
    dnp_metadata_listed: bool
    pin_assignments: tuple[UsbPeerReferenceComponentPin, ...]


@dataclass(frozen=True, slots=True)
class UsbPeerDataShuntBranch:
    data_pin: str
    reference_pin: str
    symbol: str
    data_net: str
    reference_net: str


@dataclass(frozen=True, slots=True)
class UsbPeerDataSeriesResistor:
    reference: str
    symbol: str
    footprint: str
    value: str
    connector_pin: str
    phy_pin: str
    connector_net: str
    phy_net: str


@dataclass(frozen=True, slots=True)
class UsbPeerDataInlineComponent:
    reference: str
    symbol: str
    footprint: str
    connector_pin: str
    phy_pin: str
    connector_net: str
    phy_net: str
    pin_assignments: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UsbPeerDataProtectionShuntPin:
    line: Literal["D+", "D-"]
    pin: str
    net: str


@dataclass(frozen=True, slots=True)
class UsbPeerDataProtectionShunt:
    reference: str
    symbol: str
    footprint: str
    data_pins: tuple[UsbPeerDataProtectionShuntPin, ...]
    pin_assignments: tuple[str, ...]


@dataclass(frozen=True, slots=True)
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
    positive_inline_component: UsbPeerDataInlineComponent | None = None
    negative_inline_component: UsbPeerDataInlineComponent | None = None
    protection_shunts: tuple[UsbPeerDataProtectionShunt, ...] = ()
    port_group: str | None = None
    connector_signal_family: UsbPeerSignalFamily = "USB 2.0 data"
    phy_signal_family: UsbPeerSignalFamily = "USB 2.0 data"


@dataclass(frozen=True, slots=True)
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
    reference_component_observations: tuple[UsbPeerReferenceComponentObservation, ...] = ()


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
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
    unsupported_multi_pin_paths: tuple[UsbPeerUnsupportedMultiPinPath, ...] = ()


@dataclass(frozen=True, slots=True)
class UsbPeerUnsupportedMultiPinPath:
    """Coverage-only evidence for one unmapped multi-pin USB data topology candidate."""

    connector_reference: str
    phy_reference: str
    component_reference: str
    component_symbol: str
    component_footprint: str
    component_pin_count: int
    port_group: str | None
    positive_connector_net: str
    positive_phy_net: str
    positive_connector_component_pins: tuple[str, ...]
    positive_phy_component_pins: tuple[str, ...]
    negative_connector_net: str
    negative_phy_net: str
    negative_connector_component_pins: tuple[str, ...]
    negative_phy_component_pins: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UsbPeerEndpointGroupCoverage:
    """Identity and bounded disposition for one recognized USB endpoint group."""

    endpoint_role: Literal["connector", "phy"]
    reference: str
    port_group: str | None
    disposition: Literal["SUPPORTED", "INCOMPLETE", "DNP"]
    signal_family: UsbPeerSignalFamily = "USB 2.0 data"


@dataclass(frozen=True, slots=True)
class UsbPeerReferenceScan:
    """Review candidates and applicability counts from one deterministic scan."""

    reviews: tuple[UsbPeerReferenceReview, ...]
    coverage: UsbPeerReferenceCoverage


@dataclass(frozen=True, slots=True)
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
    signal_family: UsbPeerSignalFamily = "USB 2.0 data"
