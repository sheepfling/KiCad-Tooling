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
    nets: tuple[NetName, ...] = ()


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
