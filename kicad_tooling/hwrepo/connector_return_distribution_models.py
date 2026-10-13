"""Typed requirements and evidence for connector return-contact distribution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    ElectricalPositive,
    Identifier,
    NonEmptyText,
    NonNegativeCount,
    Reference,
    StrictModel,
)


class ConnectorReturnDistributionRequirement(StrictModel):
    """Project-owned signal/return contact ratio for one reviewed interface."""

    id: Identifier
    interface_id: Identifier
    minimum_signal_pin_count: Annotated[int, Field(ge=1)]
    maximum_signal_to_return_ratio: ElectricalPositive
    basis: NonEmptyText


class ConnectorReturnDistributionMap(StrictModel):
    """Opt-in thresholds for explicitly role-classified interfaces."""

    requirements: Annotated[tuple[ConnectorReturnDistributionRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_requirements(self) -> ConnectorReturnDistributionMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Connector return-distribution IDs must be unique")
        interfaces = [item.interface_id.casefold() for item in self.requirements]
        if len(set(interfaces)) != len(interfaces):
            raise ValueError("Connector return-distribution interfaces must be unique")
        return self


class ConnectorReturnDistributionEntry(StrictModel):
    """Role counts and threshold result for one mapped connector instance."""

    id: Identifier
    connector_reference: Identifier | None = None
    interface_id: Identifier
    status: Literal["COMPLETE", "BELOW_SCOPE", "OUT_OF_RANGE", "INCOMPLETE"]
    signal_pin_map: Mapping[NonEmptyText, Reference] = Field(default_factory=dict)
    return_pin_map: Mapping[NonEmptyText, Reference] = Field(default_factory=dict)
    supply_pin_map: Mapping[NonEmptyText, Reference] = Field(default_factory=dict)
    shield_pin_map: Mapping[NonEmptyText, Reference] = Field(default_factory=dict)
    other_pin_map: Mapping[NonEmptyText, Reference] = Field(default_factory=dict)
    unclassified_pin_map: Mapping[NonEmptyText, Reference] = Field(default_factory=dict)
    signal_pin_count: NonNegativeCount
    return_pin_count: NonNegativeCount
    required_return_pin_count: NonNegativeCount
    signal_to_return_ratio: ElectricalPositive | None = None
    minimum_signal_pin_count: Annotated[int, Field(ge=1)]
    maximum_signal_to_return_ratio: ElectricalPositive
    basis: NonEmptyText
    issues: tuple[NonEmptyText, ...] = ()


class ConnectorReturnDistributionCoverageReport(StrictModel):
    """Source-bound review coverage for authored return-contact thresholds."""

    status: Literal["NOT_REQUESTED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = "NOT_REQUESTED"
    scope: NonEmptyText = (
        "Counts explicitly role-classified connector contacts for project-scoped signal/return "
        "ratios. It does not assert net equality, electrical capacity, or PCB continuity."
    )
    netlist_sha256: Digest | None = None
    interface_catalog_sha256: Digest | None = None
    entries: tuple[ConnectorReturnDistributionEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def source_bound_when_configured(self) -> ConnectorReturnDistributionCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and (
            self.netlist_sha256 is None or self.interface_catalog_sha256 is None
        ):
            raise ValueError(
                "Configured return-distribution coverage must bind netlist and interface catalog"
            )
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked return-distribution coverage must explain the evidence gap")
        return self
