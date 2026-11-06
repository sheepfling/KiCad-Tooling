"""Project-authored single-capacitor hold-up requirements."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    ElectricalPositive,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    StrictModel,
)

EffectiveFraction = Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)]


class EnergyStorageHoldUpRequirement(StrictModel):
    """A source-reviewed constant-current hold-up envelope for one capacitor."""

    id: Identifier
    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_part_id: Identifier
    pins: Annotated[tuple[Reference, Reference], Field(min_length=2, max_length=2)]
    nets: Annotated[tuple[NetName, NetName], Field(min_length=2, max_length=2)]
    minimum_start_voltage_v: ElectricalPositive
    minimum_operating_voltage_v: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    maximum_constant_load_current_a: ElectricalPositive
    minimum_hold_up_time_s: ElectricalPositive
    minimum_effective_capacitance_fraction: EffectiveFraction
    maximum_utilization_fraction: EffectiveFraction
    capacitance_source: NonEmptyText
    effective_capacitance_basis: NonEmptyText
    load_current_basis: NonEmptyText
    voltage_window_basis: NonEmptyText
    hold_up_basis: NonEmptyText

    @model_validator(mode="after")
    def exact_storage_component(self) -> EnergyStorageHoldUpRequirement:
        if any(pin.rsplit(".", 1)[0].casefold() != self.reference.casefold() for pin in self.pins):
            raise ValueError("Energy-storage pins must belong to the declared reference")
        if len({pin.casefold() for pin in self.pins}) != 2:
            raise ValueError("Energy-storage pins must be unique")
        if self.nets[0].casefold() == self.nets[1].casefold():
            raise ValueError("Energy-storage pins must map to distinct reviewed nets")
        if self.minimum_start_voltage_v <= self.minimum_operating_voltage_v:
            raise ValueError("Minimum start voltage must exceed minimum operating voltage")
        return self


class EnergyStorageAnalysis(StrictModel):
    """Project-owned exact-part capacitor hold-up requirements."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    requirements: Annotated[tuple[EnergyStorageHoldUpRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_requirements(self) -> EnergyStorageAnalysis:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Energy-storage requirement IDs must be unique")
        if len({item.reference.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Each storage capacitor may have one hold-up requirement")
        return self
