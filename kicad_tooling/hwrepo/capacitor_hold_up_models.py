"""Project-authored single-capacitor hold-up review requirements."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .capacitance_values import parse_capacitance_pf
from .model_primitives import (
    Identifier,
    NetName,
    NonEmptyText,
    PositiveMeasure,
    Reference,
    StrictModel,
)


class CapacitorHoldUpRequirement(StrictModel):
    """One exact capacitor and an authored constant-current hold-up screen."""

    id: Identifier
    basis: NonEmptyText
    capacitor_reference: Identifier
    expected_value: NonEmptyText
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_part_id: Identifier
    positive_pin: Reference
    return_pin: Reference
    positive_net: NetName
    return_net: NetName
    starting_voltage_v: PositiveMeasure
    minimum_load_voltage_v: PositiveMeasure
    maximum_load_current_ma: PositiveMeasure
    minimum_hold_up_ms: PositiveMeasure

    @field_validator("expected_value")
    @classmethod
    def value_is_supported_capacitance(cls, value: str) -> str:
        if parse_capacitance_pf(value) is None:
            raise ValueError("Expected capacitor value must use a supported positive capacitance")
        return value

    @model_validator(mode="after")
    def exact_two_pin_discharge_contract(self) -> CapacitorHoldUpRequirement:
        prefix = f"{self.capacitor_reference}.".casefold()
        if any(
            not pin.casefold().startswith(prefix) for pin in (self.positive_pin, self.return_pin)
        ):
            raise ValueError("Hold-up pins must belong to the declared capacitor")
        if self.positive_pin.casefold() == self.return_pin.casefold():
            raise ValueError("Hold-up capacitor pins must differ")
        if self.positive_net.casefold() == self.return_net.casefold():
            raise ValueError("Hold-up positive and return nets must differ")
        if self.starting_voltage_v <= self.minimum_load_voltage_v:
            raise ValueError("Starting voltage must exceed the minimum load voltage")
        return self


class CapacitorHoldUpMap(StrictModel):
    """Reviewed hold-up requirements; no operating values are inferred."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[CapacitorHoldUpRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_requirements_and_capacitors(self) -> CapacitorHoldUpMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Capacitor hold-up requirement IDs must be unique")
        if len({item.capacitor_reference.casefold() for item in self.requirements}) != len(
            self.requirements
        ):
            raise ValueError("A capacitor can appear in only one hold-up requirement")
        return self
