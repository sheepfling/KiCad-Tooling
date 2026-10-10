"""Typed source-bound reports for USB peer-reference review."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeCount,
    Reference,
    StrictModel,
    UsbDataPortGroup,
)


class UsbPeerEndpointGroupCoverage(StrictModel):
    """Identity and bounded disposition for one recognized USB endpoint group."""

    endpoint_role: Literal["connector", "phy"]
    reference: Identifier
    port_group: NonEmptyText | None = None
    disposition: Literal["SUPPORTED", "INCOMPLETE", "DNP"]


class UsbPeerReferencePinCoverage(StrictModel):
    """Observed native assignment for one connector or PHY reference pin."""

    pin: Reference
    function: NonEmptyText
    electrical_type: NonEmptyText
    net: NetName


class UsbPeerDataShuntBranchCoverage(StrictModel):
    """Observed two-pin passive branch from one USB data pin to a reference net."""

    data_pin: Reference
    reference_pin: Reference
    symbol: NonEmptyText
    data_net: NetName
    reference_net: NetName


class UsbPeerDataSeriesResistorCoverage(StrictModel):
    """Observed fitted two-pin resistor between the connector and PHY data nets."""

    reference: Identifier
    symbol: NonEmptyText
    footprint: str
    value: NonEmptyText
    connector_pin: Reference
    phy_pin: Reference
    connector_net: NetName
    phy_net: NetName


class UsbPeerDataLineCoverage(StrictModel):
    """Bounded source evidence for one positive or negative USB 2.0 data line."""

    connector_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    phy_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    connector_net: NetName
    phy_net: NetName
    series_resistor: UsbPeerDataSeriesResistorCoverage | None = None
    shunt_branches: tuple[UsbPeerDataShuntBranchCoverage, ...] = ()

    @model_validator(mode="after")
    def assignments_match_topology(self) -> UsbPeerDataLineCoverage:
        for label, pins in (("connector", self.connector_pins), ("PHY", self.phy_pins)):
            if len({item.casefold() for item in pins}) != len(pins):
                raise ValueError(f"USB {label} data pins must be unique")
        resistor = self.series_resistor
        if resistor is None:
            if self.connector_net.casefold() != self.phy_net.casefold():
                raise ValueError("USB direct data evidence must use one shared net")
        elif (
            self.connector_net.casefold() == self.phy_net.casefold()
            or resistor.connector_net.casefold() != self.connector_net.casefold()
            or resistor.phy_net.casefold() != self.phy_net.casefold()
            or resistor.connector_pin.rsplit(".", 1)[0].casefold() != resistor.reference.casefold()
            or resistor.phy_pin.rsplit(".", 1)[0].casefold() != resistor.reference.casefold()
            or resistor.connector_pin.casefold() == resistor.phy_pin.casefold()
        ):
            raise ValueError("USB series resistor evidence must join the exact endpoint nets")
        for branch in self.shunt_branches:
            if branch.data_net.casefold() not in {
                self.connector_net.casefold(),
                self.phy_net.casefold(),
            }:
                raise ValueError("USB shunt evidence must branch from a matched data net")
        return self


class UsbPeerDataPathCoverage(StrictModel):
    """Observed positive/negative line assignments for one supported USB peer path."""

    positive: UsbPeerDataLineCoverage
    negative: UsbPeerDataLineCoverage
    port_group: UsbDataPortGroup | None = None


class UsbPeerReferencePathCoverageEntry(StrictModel):
    """Exact supported connector-to-PHY path and common/split/map disposition."""

    connector_reference: Identifier
    phy_reference: Identifier
    connector_symbol: NonEmptyText
    phy_symbol: NonEmptyText
    connector_footprint: str
    phy_footprint: str
    connector_reference_net: NetName
    phy_reference_net: NetName
    connector_reference_pins: Annotated[
        tuple[UsbPeerReferencePinCoverage, ...], Field(min_length=1)
    ]
    phy_reference_pins: Annotated[tuple[UsbPeerReferencePinCoverage, ...], Field(min_length=1)]
    reference_disposition: Literal[
        "COMMON_REFERENCE",
        "SEPARATE_REFERENCE_REVIEW",
        "MAP_COVERED_SEPARATE_REFERENCE",
    ]
    data_path: UsbPeerDataPathCoverage

    @model_validator(mode="after")
    def path_assignments_match_disposition(self) -> UsbPeerReferencePathCoverageEntry:
        if self.connector_reference.casefold() == self.phy_reference.casefold():
            raise ValueError("USB peer paths must join distinct connector and PHY components")
        if any(
            item.pin.rsplit(".", 1)[0].casefold() != self.connector_reference.casefold()
            or item.net.casefold() != self.connector_reference_net.casefold()
            for item in self.connector_reference_pins
        ):
            raise ValueError("USB connector reference pins must match the path identity and net")
        if any(
            item.pin.rsplit(".", 1)[0].casefold() != self.phy_reference.casefold()
            or item.net.casefold() != self.phy_reference_net.casefold()
            for item in self.phy_reference_pins
        ):
            raise ValueError("USB PHY reference pins must match the path identity and net")
        same_reference = (
            self.connector_reference_net.casefold() == self.phy_reference_net.casefold()
        )
        if (self.reference_disposition == "COMMON_REFERENCE") != same_reference:
            raise ValueError("USB reference disposition must match the observed reference nets")
        if self.data_path.port_group is not None and not self.data_path.port_group.isdecimal():
            raise ValueError("USB peer path port groups must be decimal numbers")
        all_reference_nets = {
            self.connector_reference_net.casefold(),
            self.phy_reference_net.casefold(),
        }
        for line in (self.data_path.positive, self.data_path.negative):
            for branch in line.shunt_branches:
                if branch.reference_net.casefold() not in all_reference_nets:
                    raise ValueError(
                        "USB shunt reference evidence must use an endpoint reference net"
                    )
        return self


class UsbPeerReferenceCoverageReport(StrictModel):
    """Source-bound applicability counts for the USB reference heuristic."""

    rule_id: Literal["bus.usb_peer_reference_review"]
    status: Literal[
        "NO_USB_ENDPOINTS",
        "INCOMPLETE",
        "NO_SUPPORTED_PEER_PATHS",
        "EVALUATED",
    ]
    mode: Literal["review", "block", "off"]
    netlist_sha256: Digest
    usb_data_path_map_sha256: Digest | None = None
    # Optional for compatibility with earlier schema-version-2 reports.
    endpoint_groups: tuple[UsbPeerEndpointGroupCoverage, ...] | None = None
    path_entries: tuple[UsbPeerReferencePathCoverageEntry, ...] | None = None
    recognized_connector_group_count: NonNegativeCount = 0
    supported_connector_group_count: NonNegativeCount = 0
    recognized_phy_group_count: NonNegativeCount = 0
    supported_phy_group_count: NonNegativeCount = 0
    dnp_group_count: NonNegativeCount = 0
    incomplete_group_count: NonNegativeCount = 0
    supported_data_path_count: NonNegativeCount = 0
    common_reference_path_count: NonNegativeCount = 0
    separate_reference_path_count: NonNegativeCount = 0
    mapped_separate_reference_path_count: NonNegativeCount = 0
    candidate_group_count: NonNegativeCount = 0

    @model_validator(mode="after")
    def counts_match_scope(self) -> UsbPeerReferenceCoverageReport:
        if self.endpoint_groups is not None:
            group_keys = {
                (item.endpoint_role, item.reference.casefold(), item.port_group)
                for item in self.endpoint_groups
            }
            if len(group_keys) != len(self.endpoint_groups):
                raise ValueError("USB endpoint coverage groups must be unique")
            if self.recognized_connector_group_count != sum(
                item.endpoint_role == "connector" for item in self.endpoint_groups
            ):
                raise ValueError("USB connector group count must match endpoint coverage entries")
            if self.recognized_phy_group_count != sum(
                item.endpoint_role == "phy" for item in self.endpoint_groups
            ):
                raise ValueError("USB PHY group count must match endpoint coverage entries")
            if self.supported_connector_group_count != sum(
                item.endpoint_role == "connector" and item.disposition == "SUPPORTED"
                for item in self.endpoint_groups
            ):
                raise ValueError("Supported USB connector groups must match endpoint entries")
            if self.supported_phy_group_count != sum(
                item.endpoint_role == "phy" and item.disposition == "SUPPORTED"
                for item in self.endpoint_groups
            ):
                raise ValueError("Supported USB PHY groups must match endpoint entries")
            if self.dnp_group_count != sum(
                item.disposition == "DNP" for item in self.endpoint_groups
            ):
                raise ValueError("USB DNP group count must match endpoint entries")
            if self.incomplete_group_count != sum(
                item.disposition == "INCOMPLETE" for item in self.endpoint_groups
            ):
                raise ValueError("USB incomplete group count must match endpoint entries")
        if self.path_entries is not None:
            path_keys = tuple(
                (
                    item.connector_reference.casefold(),
                    item.phy_reference.casefold(),
                    item.data_path.port_group is not None,
                    item.data_path.port_group or "",
                )
                for item in self.path_entries
            )
            if len(set(path_keys)) != len(path_keys):
                raise ValueError("USB peer path coverage entries must be unique")
            if path_keys != tuple(sorted(path_keys)):
                raise ValueError("USB peer path coverage entries must be deterministically ordered")
            if len(self.path_entries) != self.supported_data_path_count:
                raise ValueError("USB path coverage entries must match supported data paths")
            if self.common_reference_path_count != sum(
                item.reference_disposition == "COMMON_REFERENCE" for item in self.path_entries
            ):
                raise ValueError("Common-reference paths must match path coverage entries")
            if self.separate_reference_path_count != sum(
                item.reference_disposition != "COMMON_REFERENCE" for item in self.path_entries
            ):
                raise ValueError("Separate-reference paths must match path coverage entries")
            if self.mapped_separate_reference_path_count != sum(
                item.reference_disposition == "MAP_COVERED_SEPARATE_REFERENCE"
                for item in self.path_entries
            ):
                raise ValueError("Map-covered paths must match path coverage entries")
            if self.candidate_group_count != sum(
                item.reference_disposition == "SEPARATE_REFERENCE_REVIEW"
                for item in self.path_entries
            ):
                raise ValueError("USB review candidates must match path coverage entries")
        recognized_groups = self.recognized_connector_group_count + self.recognized_phy_group_count
        supported_groups = self.supported_connector_group_count + self.supported_phy_group_count
        if supported_groups > recognized_groups:
            raise ValueError("Supported USB endpoint groups cannot exceed recognized groups")
        if (
            self.dnp_group_count + self.incomplete_group_count
            != recognized_groups - supported_groups
        ):
            raise ValueError("USB endpoint groups must be assigned DNP or incomplete dispositions")
        if self.supported_data_path_count != (
            self.common_reference_path_count + self.separate_reference_path_count
        ):
            raise ValueError("USB data-path counts must balance by reference relationship")
        if self.mapped_separate_reference_path_count > self.separate_reference_path_count:
            raise ValueError("Mapped USB paths cannot exceed separate-reference paths")
        if self.candidate_group_count != (
            self.separate_reference_path_count - self.mapped_separate_reference_path_count
        ):
            raise ValueError("USB review candidates must match unmapped separate-reference paths")
        expected_status = (
            "NO_USB_ENDPOINTS"
            if recognized_groups == 0
            else "INCOMPLETE"
            if self.incomplete_group_count > 0
            else "NO_SUPPORTED_PEER_PATHS"
            if self.supported_data_path_count == 0
            else "EVALUATED"
        )
        if self.status != expected_status:
            raise ValueError("USB peer-reference coverage status does not match its counts")
        return self
