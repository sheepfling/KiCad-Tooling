"""Typed source and load membership requirements for named power rails."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, Reference, StrictModel


class PowerPinEndpointRequirement(StrictModel):
    """Reviewed component identity and pins assigned to one authored rail role."""

    id: Identifier
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    pins: Annotated[tuple[Reference, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def endpoint_pins_are_local_and_unique(self) -> PowerPinEndpointRequirement:
        if any(pin.rsplit(".", 1)[0].casefold() != self.reference.casefold() for pin in self.pins):
            raise ValueError("Power endpoint pins must belong to the declared component")
        if len({pin.casefold() for pin in self.pins}) != len(self.pins):
            raise ValueError("Power endpoint pins must be unique")
        return self


class PowerSourceGroupRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    selection: Literal["all", "any"]
    endpoints: Annotated[tuple[PowerPinEndpointRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_source_endpoints(self) -> PowerSourceGroupRequirement:
        if len({item.id.casefold() for item in self.endpoints}) != len(self.endpoints):
            raise ValueError("Power source endpoint IDs must be unique within a group")
        if len({item.reference.casefold() for item in self.endpoints}) != len(self.endpoints):
            raise ValueError("A power source group cannot repeat a component reference")
        return self


class PowerLoadConnectivityRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    endpoints: Annotated[tuple[PowerPinEndpointRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_load_endpoints(self) -> PowerLoadConnectivityRequirement:
        if len({item.id.casefold() for item in self.endpoints}) != len(self.endpoints):
            raise ValueError("Power load endpoint IDs must be unique within a load")
        if len({item.reference.casefold() for item in self.endpoints}) != len(self.endpoints):
            raise ValueError("A power load cannot repeat a component reference")
        return self


class PowerConnectivityRailRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    net: NetName
    source_groups: Annotated[tuple[PowerSourceGroupRequirement, ...], Field(min_length=1)]
    loads: Annotated[tuple[PowerLoadConnectivityRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def distinct_rail_relationships(self) -> PowerConnectivityRailRequirement:
        if len({item.id.casefold() for item in self.source_groups}) != len(self.source_groups):
            raise ValueError("Power source group IDs must be unique within a rail")
        if len({item.id.casefold() for item in self.loads}) != len(self.loads):
            raise ValueError("Power load IDs must be unique within a rail")
        pins = [
            pin.casefold()
            for group in self.source_groups
            for endpoint in group.endpoints
            for pin in endpoint.pins
        ]
        pins.extend(
            pin.casefold()
            for load in self.loads
            for endpoint in load.endpoints
            for pin in endpoint.pins
        )
        if len(set(pins)) != len(pins):
            raise ValueError("A power endpoint pin cannot be assigned more than once per rail")
        return self


class PowerConnectivityAnalysis(StrictModel):
    """Project-authored source and load pin membership for named power rails."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    rails: Annotated[tuple[PowerConnectivityRailRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_rails_and_endpoint_pins(self) -> PowerConnectivityAnalysis:
        if len({item.id.casefold() for item in self.rails}) != len(self.rails):
            raise ValueError("Power connectivity rail IDs must be unique")
        if len({item.net for item in self.rails}) != len(self.rails):
            raise ValueError("Power connectivity rails must use distinct net names")
        pins = [
            pin.casefold()
            for rail in self.rails
            for group in rail.source_groups
            for endpoint in group.endpoints
            for pin in endpoint.pins
        ]
        pins.extend(
            pin.casefold()
            for rail in self.rails
            for load in rail.loads
            for endpoint in load.endpoints
            for pin in endpoint.pins
        )
        if len(set(pins)) != len(pins):
            raise ValueError("A power endpoint pin cannot be assigned to multiple rails or roles")
        return self
