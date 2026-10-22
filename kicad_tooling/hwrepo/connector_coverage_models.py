"""Typed connector inventory and pin-mapping coverage records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field, model_validator

from .connector_peer_pin_models import ConnectorPinRole
from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    RepositoryPath,
    StrictModel,
)


class ConnectorMappedPinEvidence(StrictModel):
    interface_pin_number: NonEmptyText
    interface_signal: NonEmptyText
    component_pin: Reference
    role: ConnectorPinRole | None = None
    voltage_domain: NonEmptyText | None = None
    symbol_function: NonEmptyText | None = None
    unconnected_reason: NonEmptyText | None = None
    nets: tuple[NetName, ...] = ()


class ConnectorInterfaceReview(StrictModel):
    """Project-owned pinout and intentional-open decisions for one connector."""

    reference: Identifier
    disposition: Literal["interface", "not_applicable"]
    basis: NonEmptyText
    interface_id: Identifier | None = None
    pin_map: Mapping[NonEmptyText, NonEmptyText] = Field(default_factory=dict)
    unlisted_pin_reasons: Mapping[NonEmptyText, NonEmptyText] = Field(default_factory=dict)
    unconnected_pin_reasons: Mapping[NonEmptyText, NonEmptyText] = Field(default_factory=dict)
    peer_assignment_group: Identifier | None = None
    peer_assignment_basis: NonEmptyText | None = None

    @model_validator(mode="after")
    def complete_disposition(self) -> ConnectorInterfaceReview:
        if self.disposition == "interface":
            if self.interface_id is None or not self.pin_map:
                raise ValueError("Interface review needs an interface ID and a pin map")
            targets = tuple(self.pin_map.values())
            if len(set(targets)) != len(targets):
                raise ValueError("Interface pin map must use each component pin at most once")
            if set(targets) & set(self.unlisted_pin_reasons):
                raise ValueError("A component pin cannot be mapped and listed as unlisted")
            if not set(self.unconnected_pin_reasons) <= set(targets):
                raise ValueError("Unconnected-pin reasons must name mapped component pins")
        elif (
            self.interface_id is not None
            or self.pin_map
            or self.unlisted_pin_reasons
            or self.unconnected_pin_reasons
            or self.peer_assignment_group is not None
            or self.peer_assignment_basis is not None
        ):
            raise ValueError("Not-applicable review cannot contain interface or peer-group data")
        if (self.peer_assignment_group is None) != (self.peer_assignment_basis is None):
            raise ValueError("Connector peer-assignment groups need a review basis")
        return self


class ConnectorInventoryReview(StrictModel):
    """Project-owned basis for a complete connector-reference inventory review."""

    basis: NonEmptyText


class ConnectorCoverageEntry(StrictModel):
    reference: Identifier
    status: Literal["COVERED", "NOT_APPLICABLE", "UNDECLARED", "INCOMPLETE", "STALE"]
    interface_id: Identifier | None = None
    basis: NonEmptyText | None = None
    peer_assignment_group: Identifier | None = None
    peer_assignment_basis: NonEmptyText | None = None
    interface_pin_map: Mapping[NonEmptyText, NonEmptyText] = Field(default_factory=dict)
    unlisted_pin_reasons: Mapping[NonEmptyText, NonEmptyText] = Field(default_factory=dict)
    mapped_pins: tuple[ConnectorMappedPinEvidence, ...] = ()
    interface_pins_unmapped: tuple[NonEmptyText, ...] = ()
    interface_pins_unknown: tuple[NonEmptyText, ...] = ()
    component_pins_unaccounted: tuple[NonEmptyText, ...] = ()
    component_pins_unknown: tuple[NonEmptyText, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def complete_peer_assignment_group(self) -> ConnectorCoverageEntry:
        if (self.peer_assignment_group is None) != (self.peer_assignment_basis is None):
            raise ValueError("Connector peer-assignment groups need a review basis")
        if self.status == "NOT_APPLICABLE" and self.peer_assignment_group is not None:
            raise ValueError("Not-applicable connectors cannot join a peer-assignment group")
        return self


class ConnectorCoverageReport(StrictModel):
    """Coverage of explicitly identified or heuristically discovered connector candidates."""

    status: Literal["COMPLETE", "INCOMPLETE", "UNDECLARED", "UNASSESSED", "SCOPE_UNREVIEWED"]
    scope: NonEmptyText
    project_interfaces: tuple[Identifier, ...] = ()
    unbound_interface_ids: tuple[Identifier, ...] = ()
    inventory_review_basis: NonEmptyText | None = None
    interface_catalog_path: RepositoryPath | None = None
    interface_catalog_sha256: Digest | None = None
    entries: tuple[ConnectorCoverageEntry, ...] = ()
    catalog_issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def inventory_review_matches_status(self) -> ConnectorCoverageReport:
        if self.status == "COMPLETE" and self.inventory_review_basis is None:
            raise ValueError("Complete connector coverage requires an inventory review basis")
        if self.status in {"UNASSESSED", "SCOPE_UNREVIEWED"} and (
            self.inventory_review_basis is not None
        ):
            raise ValueError(f"{self.status} connector coverage cannot include an inventory basis")
        return self
