"""Typed authored rail, budget, and observed net membership review."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .model_primitives import (
    Digest,
    FiniteMeasure,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    RepositoryPath,
    StrictModel,
)
from .netlist_membership import PinStatus


class PowerTreePin(StrictModel):
    pin: Reference
    observed_nets: tuple[NetName, ...] = ()
    status: PinStatus


class PowerTreeEndpoint(StrictModel):
    id: Identifier
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    observed_component: Literal["RETAINED", "MISSING", "UNREVIEWED"]
    observed_symbol: str | None = None
    observed_footprint: str | None = None
    observed_dnp: bool | None = None
    pins: tuple[PowerTreePin, ...]


class PowerTreeRelationship(StrictModel):
    id: Identifier
    basis: NonEmptyText
    role: Literal["SOURCE_GROUP", "LOAD"]
    selection: Literal["all", "any"] | None = None
    check_status: Literal["PASS", "FAIL", "UNREVIEWED"]
    check_detail: NonEmptyText
    endpoints: tuple[PowerTreeEndpoint, ...]
    steady_a: FiniteMeasure | None = None
    startup_a: FiniteMeasure | None = None
    startup_s: FiniteMeasure | None = None


class PowerTreeBudget(StrictModel):
    voltage_v: FiniteMeasure
    continuous_limit_a: FiniteMeasure
    peak_limit_a: FiniteMeasure
    peak_duration_limit_s: FiniteMeasure
    steady_demand_a: FiniteMeasure
    startup_demand_a: FiniteMeasure
    startup_duration_assessed_s: FiniteMeasure
    steady_status: Literal["PASS", "FAIL"]
    startup_status: Literal["PASS", "FAIL"]
    duration_status: Literal["PASS", "FAIL"]


class PowerTreeViewReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["POWER_TREE_VIEW"] = "POWER_TREE_VIEW"
    build_authorized: Literal[False] = False
    project_id: Identifier
    rail_id: Identifier
    net: NetName
    basis: NonEmptyText
    analysis_status: Literal["PASS", "FAIL", "NOT_CONFIGURED"]
    source_receipt: RepositoryPath
    source_report_sha256: Digest
    requirements_sha256: Digest
    observed_sha256: Digest | None = None
    native_netlist_sha256: Digest | None = None
    analysis_source_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    observation_status: Literal["RETAINED", "UNREVIEWED"]
    source_status: Literal["CURRENT", "STALE", "UNKNOWN", "UNAVAILABLE"] = "UNKNOWN"
    source_groups: tuple[PowerTreeRelationship, ...]
    loads: tuple[PowerTreeRelationship, ...]
    undeclared_pins: tuple[PowerTreePin, ...]
    budget: PowerTreeBudget | None = None
    output_directory: str
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
