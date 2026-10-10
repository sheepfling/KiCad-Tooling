"""Typed coverage model for digital peer-voltage analysis."""

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
    RepositoryPath,
    StrictModel,
)
from .serial_logic_models import SerialLogicInputLimits, SerialLogicOutputLimits


class DigitalPeerVoltageRuleCoverage(StrictModel):
    """Applicability counts for one named-function direct-peer voltage heuristic."""

    rule_id: Literal["bus.spi_peer_voltage_review", "bus.serial_peer_voltage_review"]
    status: Literal["NO_SUPPORTED_ENDPOINTS", "NO_DIRECT_PEERS", "INCOMPLETE", "EVALUATED"]
    mode: Literal["review", "block", "off"]
    netlist_sha256: Digest
    authored_map_state: Literal["not_configured", "pending", "not_applicable", "required"]
    authored_map_path: RepositoryPath | None = None
    authored_map_sha256: Digest | None = None
    recognized_endpoint_count: NonNegativeCount = 0
    assigned_endpoint_count: NonNegativeCount = 0
    direct_peer_link_count: NonNegativeCount = 0
    voltage_comparison_count: NonNegativeCount = 0
    same_voltage_link_count: NonNegativeCount = 0
    different_voltage_link_count: NonNegativeCount = 0
    mapped_mismatch_link_count: NonNegativeCount = 0
    candidate_group_count: NonNegativeCount = 0

    @model_validator(mode="after")
    def counts_match_scope(self) -> DigitalPeerVoltageRuleCoverage:
        if (self.authored_map_path is None) != (self.authored_map_sha256 is None):
            raise ValueError("Digital-peer voltage map path and hash must be recorded together")
        if self.assigned_endpoint_count > self.recognized_endpoint_count:
            raise ValueError("Assigned digital-peer endpoints cannot exceed recognized endpoints")
        if self.direct_peer_link_count < self.voltage_comparison_count:
            raise ValueError("Voltage comparisons cannot exceed direct peer links")
        if self.voltage_comparison_count != (
            self.same_voltage_link_count + self.different_voltage_link_count
        ):
            raise ValueError("Digital-peer voltage comparison counts do not balance")
        if self.mapped_mismatch_link_count > self.different_voltage_link_count:
            raise ValueError("Mapped voltage mismatches cannot exceed different-voltage links")
        if self.candidate_group_count > (
            self.different_voltage_link_count - self.mapped_mismatch_link_count
        ):
            raise ValueError("Candidate groups must be supported by uncovered mismatched links")

        expected_status = (
            "NO_SUPPORTED_ENDPOINTS"
            if self.recognized_endpoint_count == 0
            else "INCOMPLETE"
            if self.assigned_endpoint_count < self.recognized_endpoint_count
            or self.voltage_comparison_count < self.direct_peer_link_count
            else "NO_DIRECT_PEERS"
            if self.direct_peer_link_count == 0
            else "EVALUATED"
        )
        if self.status != expected_status:
            raise ValueError("Digital-peer voltage coverage status does not match its counts")
        return self


class DigitalLogicOutputLimits(SerialLogicOutputLimits):
    """Guaranteed output ranges for a mapped direct digital peer."""


class DigitalLogicInputLimits(SerialLogicInputLimits):
    """Receiver thresholds and absolute limits for a mapped digital peer."""


class DigitalPeerPinRequirement(StrictModel):
    """Exact, source-bound identity and net assignment for one peer pin."""

    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    pin: Reference
    net: NetName

    @model_validator(mode="after")
    def pin_belongs_to_component(self) -> DigitalPeerPinRequirement:
        if (
            "." not in self.pin
            or self.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
        ):
            raise ValueError("Digital peer pin must be qualified by its declared component")
        return self


class DigitalPeerVoltageLink(StrictModel):
    """One reviewed, directly connected output-to-input relationship."""

    id: Identifier
    basis: NonEmptyText
    driver: DigitalPeerPinRequirement
    receiver: DigitalPeerPinRequirement
    output_limits: DigitalLogicOutputLimits | None = None
    input_limits: DigitalLogicInputLimits | None = None

    @model_validator(mode="after")
    def direct_peer_pin_map(self) -> DigitalPeerVoltageLink:
        if self.driver.reference.casefold() == self.receiver.reference.casefold():
            raise ValueError("Digital peer endpoints must be distinct components")
        if self.driver.pin.casefold() == self.receiver.pin.casefold():
            raise ValueError("Digital peer endpoints must use distinct pins")
        if self.driver.net != self.receiver.net:
            raise ValueError("Direct digital peer endpoints must declare the same net")
        return self


class DigitalPeerVoltageAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    basis: NonEmptyText
    links: Annotated[tuple[DigitalPeerVoltageLink, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_link_ids(self) -> DigitalPeerVoltageAnalysis:
        if len({link.id.casefold() for link in self.links}) != len(self.links):
            raise ValueError("Digital peer link IDs must be unique")
        return self
