"""Typed power path contract records."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, Reference, StrictModel


class PowerPathEndpointRequirement(StrictModel):
    """One exact endpoint in a project-authored series power-path map."""

    reference: Identifier
    pin: Reference
    symbol: NonEmptyText
    footprint: NonEmptyText
    net: NetName
    role: Literal["endpoint", "current_controlled_sink"] = "endpoint"
    part_id: Identifier | None = None
    pin_function: NonEmptyText | None = None
    pin_electrical_type: NonEmptyText | None = None

    @model_validator(mode="after")
    def endpoint_pin_belongs_to_component(self) -> PowerPathEndpointRequirement:
        if (
            "." not in self.pin
            or self.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
        ):
            raise ValueError("Power-path endpoint pin must belong to its declared component")
        exact_signature = (self.part_id, self.pin_function, self.pin_electrical_type)
        if any(item is not None for item in exact_signature) and not all(
            item is not None for item in exact_signature
        ):
            raise ValueError(
                "Power-path endpoint part ID, pin function, and electrical type must be supplied together"
            )
        if self.role == "current_controlled_sink":
            electrical_type = self.pin_electrical_type
            if self.part_id is None or self.pin_function is None or electrical_type is None:
                raise ValueError(
                    "A current-controlled sink endpoint requires exact part ID, pin function, "
                    "and electrical type evidence"
                )
            if electrical_type.casefold() not in {
                "output",
                "bidirectional",
                "tri_state",
                "open_collector",
                "open_emitter",
                "open_drain",
            }:
                raise ValueError(
                    "A current-controlled sink endpoint requires an output-capable native pin type"
                )
        return self


class PowerPathElementRequirement(StrictModel):
    """One fitted two-terminal component required between adjacent power nets."""

    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    side_a_pin: Reference
    side_b_pin: Reference
    side_a_net: NetName
    side_b_net: NetName

    @model_validator(mode="after")
    def valid_component_sides(self) -> PowerPathElementRequirement:
        if self.side_a_pin.casefold() == self.side_b_pin.casefold():
            raise ValueError("Power-path component sides must use distinct pins")
        for pin in (self.side_a_pin, self.side_b_pin):
            if "." not in pin or pin.rsplit(".", 1)[0].casefold() != self.reference.casefold():
                raise ValueError("Power-path component pins must belong to the declared component")
        if self.side_a_net == self.side_b_net:
            raise ValueError("Power-path component sides must span distinct nets")
        return self


class PowerPathRequirement(StrictModel):
    """Exact ordered netlist membership for a required, component-mediated path."""

    id: Identifier
    basis: NonEmptyText
    start: PowerPathEndpointRequirement
    end: PowerPathEndpointRequirement
    elements: Annotated[tuple[PowerPathElementRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def continuous_unique_path(self) -> PowerPathRequirement:
        if self.start.role == "current_controlled_sink":
            raise ValueError("A current-controlled sink must terminate a mapped power path")
        if self.start.pin.casefold() == self.end.pin.casefold():
            raise ValueError("Power-path endpoint pins must be distinct")
        if self.start.net == self.end.net:
            raise ValueError("A mapped series power path must span distinct endpoint nets")
        references = [
            self.start.reference.casefold(),
            self.end.reference.casefold(),
            *(item.reference.casefold() for item in self.elements),
        ]
        if len(set(references)) != len(references):
            raise ValueError("Power-path component references must be unique within a path")
        pins = [
            self.start.pin.casefold(),
            self.end.pin.casefold(),
            *(
                pin.casefold()
                for item in self.elements
                for pin in (item.side_a_pin, item.side_b_pin)
            ),
        ]
        if len(set(pins)) != len(pins):
            raise ValueError("Power-path endpoint and element pins must be unique")
        nets = [self.start.net]
        expected_net = self.start.net
        for element in self.elements:
            if element.side_a_net != expected_net:
                raise ValueError("Power-path elements must form one ordered net chain")
            expected_net = element.side_b_net
            nets.append(expected_net)
        if expected_net != self.end.net:
            raise ValueError("Power-path elements must end on the declared endpoint net")
        if len(set(nets)) != len(nets):
            raise ValueError("Power-path nets must not repeat")
        return self


class PowerPathMap(StrictModel):
    """Project-authored exact identity and pin/net map for required power paths."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    paths: Annotated[tuple[PowerPathRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_path_ids(self) -> PowerPathMap:
        if len({item.id.casefold() for item in self.paths}) != len(self.paths):
            raise ValueError("Power-path IDs must be unique")
        return self
