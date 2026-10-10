"""Typed power sequence contract records."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, Reference, StrictModel


class PowerSequenceEndpointRequirement(StrictModel):
    """One project-authored regulator endpoint in a power-sequence map."""

    reference: Identifier
    pin: Reference
    symbol: NonEmptyText
    footprint: NonEmptyText
    net: NetName
    part_id: Identifier | None = None

    @model_validator(mode="after")
    def endpoint_pin_belongs_to_component(self) -> PowerSequenceEndpointRequirement:
        if (
            "." not in self.pin
            or self.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
        ):
            raise ValueError("Power-sequence endpoint pin must belong to its declared component")
        return self


class PowerSequenceStageRequirement(StrictModel):
    """Exact output and optional enable/power-good pins for one named rail stage."""

    id: Identifier
    output: PowerSequenceEndpointRequirement
    power_good: PowerSequenceEndpointRequirement | None = None
    enable: PowerSequenceEndpointRequirement | None = None
    enable_control: Literal["netlist", "firmware", "external", "always_on", "unmodeled"]
    basis: NonEmptyText

    @model_validator(mode="after")
    def stage_endpoints_match_component(self) -> PowerSequenceStageRequirement:
        endpoints = tuple(
            item for item in (self.output, self.power_good, self.enable) if item is not None
        )
        identity = (
            self.output.reference,
            self.output.symbol,
            self.output.footprint,
            self.output.part_id,
        )
        if any(
            (item.reference, item.symbol, item.footprint, item.part_id) != identity
            for item in endpoints
        ):
            raise ValueError("Power-sequence stage endpoints must identify the same component")
        pins = [item.pin.casefold() for item in endpoints]
        if len(set(pins)) != len(pins):
            raise ValueError("Power-sequence stage endpoint pins must be unique")
        if self.enable_control == "netlist" and self.enable is None:
            raise ValueError(
                "A netlist-controlled power-sequence stage requires an enable endpoint"
            )
        return self


class PowerSequenceDependencyRequirement(StrictModel):
    """One required upstream power-good to downstream enable dependency."""

    id: Identifier
    predecessor_stage: Identifier
    successor_stage: Identifier
    signal_net: NetName
    basis: NonEmptyText

    @model_validator(mode="after")
    def distinct_stages(self) -> PowerSequenceDependencyRequirement:
        if self.predecessor_stage.casefold() == self.successor_stage.casefold():
            raise ValueError("A power-sequence dependency must connect two different stages")
        return self


class PowerSequenceMap(StrictModel):
    """Project-authored power-good-to-enable dependencies; no pin-name inference."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    stages: Annotated[tuple[PowerSequenceStageRequirement, ...], Field(min_length=2)]
    dependencies: Annotated[tuple[PowerSequenceDependencyRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_resolved_dependencies(self) -> PowerSequenceMap:
        stage_ids = {item.id.casefold() for item in self.stages}
        if len(stage_ids) != len(self.stages):
            raise ValueError("Power-sequence stage IDs must be unique")
        dependency_ids = [item.id.casefold() for item in self.dependencies]
        if len(set(dependency_ids)) != len(dependency_ids):
            raise ValueError("Power-sequence dependency IDs must be unique")
        dependency_pairs = [
            (item.predecessor_stage.casefold(), item.successor_stage.casefold())
            for item in self.dependencies
        ]
        if len(set(dependency_pairs)) != len(dependency_pairs):
            raise ValueError("Power-sequence stage dependency pairs must be unique")
        stages = {item.id.casefold(): item for item in self.stages}
        for item in self.dependencies:
            predecessor = stages.get(item.predecessor_stage.casefold())
            successor = stages.get(item.successor_stage.casefold())
            if predecessor is None or successor is None:
                raise ValueError("Power-sequence dependencies must name declared stages")
            if predecessor.power_good is None:
                raise ValueError(
                    f"Power-sequence predecessor {predecessor.id} requires a mapped power-good endpoint"
                )
            if successor.enable is None:
                raise ValueError(
                    f"Power-sequence successor {successor.id} requires a mapped enable endpoint"
                )
            if predecessor.power_good.net != item.signal_net:
                raise ValueError("Power-sequence dependency net must match its power-good endpoint")
            if successor.enable.net != item.signal_net:
                raise ValueError("Power-sequence dependency net must match its enable endpoint")
        return self
