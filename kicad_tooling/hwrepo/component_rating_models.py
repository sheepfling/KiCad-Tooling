"""Typed project-authored component voltage and power rating contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    ElectricalPositive,
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeMeasure,
    Reference,
    StrictModel,
)


class ComponentVoltageRatingRequirement(StrictModel):
    """Reviewed voltage rating and operating-stress envelope for one exact part."""

    id: Identifier
    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_part_id: Identifier
    pins: Annotated[tuple[Reference, Reference], Field(min_length=2, max_length=2)]
    nets: Annotated[tuple[NetName, NetName], Field(min_length=2, max_length=2)]
    rated_working_voltage_v: ElectricalPositive
    maximum_expected_voltage_v: NonNegativeMeasure
    maximum_utilization_fraction: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)]
    rating_source: NonEmptyText
    rating_conditions: NonEmptyText
    stress_basis: NonEmptyText

    @model_validator(mode="after")
    def exact_component_pin_pair(self) -> ComponentVoltageRatingRequirement:
        if any(pin.rsplit(".", 1)[0].casefold() != self.reference.casefold() for pin in self.pins):
            raise ValueError("Component voltage-rating pins must belong to the declared reference")
        if len({pin.casefold() for pin in self.pins}) != 2:
            raise ValueError("Component voltage-rating pins must be unique")
        return self


class ComponentVoltageRatingAnalysis(StrictModel):
    """Project-owned exact-part voltage-rating and stress comparisons."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    requirements: Annotated[tuple[ComponentVoltageRatingRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_parts(self) -> ComponentVoltageRatingAnalysis:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Component voltage-rating requirement IDs must be unique")
        if len({item.reference.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Each component may have one voltage-rating requirement")
        return self


class ComponentPowerRatingRequirement(StrictModel):
    """Reviewed power rating and dissipation envelope for one exact two-pin part."""

    id: Identifier
    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_part_id: Identifier
    pins: Annotated[tuple[Reference, Reference], Field(min_length=2, max_length=2)]
    nets: Annotated[tuple[NetName, NetName], Field(min_length=2, max_length=2)]
    rated_power_w: ElectricalPositive
    derated_allowable_power_w: ElectricalPositive
    maximum_expected_power_w: NonNegativeMeasure
    maximum_utilization_fraction: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)]
    rating_source: NonEmptyText
    rating_conditions: NonEmptyText
    derating_basis: NonEmptyText
    stress_basis: NonEmptyText

    @model_validator(mode="after")
    def exact_component_pin_pair(self) -> ComponentPowerRatingRequirement:
        if any(pin.rsplit(".", 1)[0].casefold() != self.reference.casefold() for pin in self.pins):
            raise ValueError("Component power-rating pins must belong to the declared reference")
        if len({pin.casefold() for pin in self.pins}) != 2:
            raise ValueError("Component power-rating pins must be unique")
        if self.derated_allowable_power_w > self.rated_power_w:
            raise ValueError("Derated allowable power cannot exceed the source-rated power")
        return self


class ComponentPowerRatingAnalysis(StrictModel):
    """Project-owned exact-part power-rating and dissipation comparisons."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    requirements: Annotated[tuple[ComponentPowerRatingRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_parts(self) -> ComponentPowerRatingAnalysis:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Component power-rating requirement IDs must be unique")
        if len({item.reference.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Each component may have one power-rating requirement")
        return self
