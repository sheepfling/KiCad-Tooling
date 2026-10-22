"""Project-authored PCB test-access requirement and probe-request models."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .analysis_state_models import AnalysisNotApplicable, AnalysisPending
from .model_primitives import (
    ElectricalPositive,
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeMeasure,
    Reference,
    StrictModel,
)


class TestAccessProbeEnvelope(StrictModel):
    """Project-approved circular probe tip and edge-clearance envelope."""

    tip_diameter_mm: ElectricalPositive
    clearance_mm: NonNegativeMeasure


class PcbAccessProbeRequest(StrictModel):
    """One exact test-access pad surface requested from the native PCB probe."""

    endpoint: Reference
    net: NetName
    side: Literal["front", "back"]


class PcbAccessProbeRequestSet(StrictModel):
    """Canonical set of native geometry requests retained with a PCB receipt."""

    schema_version: Literal["1"] = "1"
    requests: Annotated[tuple[PcbAccessProbeRequest, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_endpoint_surfaces(self) -> PcbAccessProbeRequestSet:
        keys = [(item.endpoint.casefold(), item.side.casefold()) for item in self.requests]
        if len(set(keys)) != len(keys):
            raise ValueError("Native probe requests must have unique endpoint surfaces")
        return self


class TestAccessEndpointRequirement(StrictModel):
    """Exact schematic pin and PCB approach surface for an approved access point."""

    kind: Literal["test_point", "programming_connector", "factory_connector"]
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    pin: Reference
    electrical_type: NonEmptyText
    approach_side: Literal["front", "back", "either"] = Field(
        default="either",
        description="Required outer PCB surface with copper and solder-mask access.",
    )
    probe_envelope: TestAccessProbeEnvelope | None = None

    @model_validator(mode="after")
    def pin_belongs_to_component(self) -> TestAccessEndpointRequirement:
        if (
            "." not in self.pin
            or self.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
        ):
            raise ValueError("Test-access pin must belong to its named component")
        return self


class RequiredTestAccess(StrictModel):
    """One exact required net and its approved schematic access endpoint(s)."""

    mode: Literal["required"]
    id: Identifier
    basis: NonEmptyText
    net: NetName
    selection: Literal["all", "any"] = "all"
    endpoints: Annotated[tuple[TestAccessEndpointRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_endpoint_pins(self) -> RequiredTestAccess:
        pins = [item.pin.casefold() for item in self.endpoints]
        if len(set(pins)) != len(pins):
            raise ValueError("Test-access endpoint pins must be unique")
        return self


class ExcludedTestAccess(StrictModel):
    """Explicitly reviewed net for which this board does not require test access."""

    mode: Literal["not_required"]
    id: Identifier
    basis: NonEmptyText
    net: NetName
    reason: NonEmptyText


TestAccessDecision = Annotated[
    RequiredTestAccess | ExcludedTestAccess,
    Field(discriminator="mode"),
]


class PcbAccessAnalysis(StrictModel):
    """Require exact approved schematic endpoints to map to PCB pad layers."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText


class TestAccessAnalysis(StrictModel):
    """Project-authored schematic test-point and programming-access requirements."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    decisions: Annotated[tuple[TestAccessDecision, ...], Field(min_length=1)]
    pcb_accessibility: Annotated[
        PcbAccessAnalysis | AnalysisNotApplicable | AnalysisPending,
        Field(discriminator="mode"),
    ]

    @model_validator(mode="after")
    def unique_ids_and_scoped_nets(self) -> TestAccessAnalysis:
        if len({item.id.casefold() for item in self.decisions}) != len(self.decisions):
            raise ValueError("Test-access decision IDs must be unique")
        if len({item.net.casefold() for item in self.decisions}) != len(self.decisions):
            raise ValueError("Each test-access net needs one explicit decision")
        if any(
            endpoint.probe_envelope is not None
            for decision in self.decisions
            if isinstance(decision, RequiredTestAccess)
            for endpoint in decision.endpoints
        ) and not isinstance(self.pcb_accessibility, PcbAccessAnalysis):
            raise ValueError("Probe envelopes require the PCB accessibility stage")
        return self
