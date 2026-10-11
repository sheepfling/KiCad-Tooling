"""Typed pin maps for exact USB multi-pin component requirements."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, Reference, StrictModel


class UsbDataPathInlinePinRequirement(StrictModel):
    """Exact expected net or explicit no-connect state for one inline-device pin."""

    pin: Reference
    disposition: Literal["net", "unconnected"]
    net: NetName | None = None

    @model_validator(mode="after")
    def disposition_matches_net(self) -> UsbDataPathInlinePinRequirement:
        if "." not in self.pin:
            raise ValueError("USB inline-component pins must use COMPONENT.PIN form")
        if self.disposition == "net" and self.net is None:
            raise ValueError("Connected USB inline-component pins need an expected net")
        if self.disposition == "unconnected" and self.net is not None:
            raise ValueError("Unconnected USB inline-component pins cannot declare a net")
        return self


class UsbDataPathProtectionShuntDataPinRequirement(StrictModel):
    """One exact data-line tap pin on a mapped multi-pin USB protection device."""

    pin: Reference
    line: Literal["D+", "D-"]
    net: NetName

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("USB protection-shunt data pins must use COMPONENT.PIN form")
        return value


class UsbDataPathProtectionShuntRequirement(StrictModel):
    """Reviewed identity and complete pin map for a multi-pin USB data shunt."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    data_pins: Annotated[
        tuple[UsbDataPathProtectionShuntDataPinRequirement, ...],
        Field(min_length=2, max_length=2),
    ]
    pins: Annotated[tuple[UsbDataPathInlinePinRequirement, ...], Field(min_length=3)]

    @model_validator(mode="after")
    def complete_distinct_component_pin_map(self) -> UsbDataPathProtectionShuntRequirement:
        reference_prefix = f"{self.reference}.".casefold()
        mapped_pin_ids = tuple(item.pin.casefold() for item in self.pins)
        if any(not item.pin.casefold().startswith(reference_prefix) for item in self.pins):
            raise ValueError("USB protection-shunt pin maps must belong to the declared component")
        if len(set(mapped_pin_ids)) != len(mapped_pin_ids):
            raise ValueError("USB protection-shunt pin maps must be unique")
        data_pin_ids = tuple(item.pin.casefold() for item in self.data_pins)
        if any(not item.pin.casefold().startswith(reference_prefix) for item in self.data_pins):
            raise ValueError("USB protection-shunt data pins must belong to the declared component")
        if len(set(data_pin_ids)) != len(data_pin_ids):
            raise ValueError("USB protection-shunt data pins must be unique")
        if {item.line for item in self.data_pins} != {"D+", "D-"}:
            raise ValueError("USB protection shunts must map exactly one D+ and one D- pin")
        if not set(data_pin_ids) <= set(mapped_pin_ids):
            raise ValueError("USB protection-shunt pin inventory must include every data pin")
        pin_requirements = {item.pin.casefold(): item for item in self.pins}
        for data_pin in self.data_pins:
            expected = pin_requirements[data_pin.pin.casefold()]
            if expected.disposition != "net" or expected.net is None:
                raise ValueError("USB protection-shunt data pins must have an expected net")
            if expected.net.casefold() != data_pin.net.casefold():
                raise ValueError("USB protection-shunt data pin net must match its pin map")
        return self
