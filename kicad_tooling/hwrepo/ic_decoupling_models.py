"""Project-authored nominal decoupling requirements for exact IC power pins."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    CapacitancePf,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    StrictModel,
)


class IcDecouplingCapacitorRequirement(StrictModel):
    """One exact two-pin capacitor expected across an IC rail and its return."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    power_pin: Reference
    return_pin: Reference

    @model_validator(mode="after")
    def pins_belong_to_capacitor(self) -> IcDecouplingCapacitorRequirement:
        prefix = f"{self.reference}.".casefold()
        if any(not pin.casefold().startswith(prefix) for pin in (self.power_pin, self.return_pin)):
            raise ValueError("Decoupling-capacitor pins must belong to the declared component")
        if self.power_pin.casefold() == self.return_pin.casefold():
            raise ValueError("Decoupling-capacitor power and return pins must differ")
        return self


class IcDecouplingRequirement(StrictModel):
    """Reviewed nominal-capacitance minimum for one exact IC supply pin."""

    id: Identifier
    basis: NonEmptyText
    ic_reference: Identifier
    expected_ic_value: NonEmptyText
    expected_ic_symbol: NonEmptyText
    expected_ic_footprint: NonEmptyText
    power_pin: Reference
    power_net: NetName
    return_net: NetName
    minimum_total_capacitance_pf: CapacitancePf
    capacitors: Annotated[tuple[IcDecouplingCapacitorRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def exact_unique_power_pin_and_capacitors(self) -> IcDecouplingRequirement:
        if not self.power_pin.casefold().startswith(f"{self.ic_reference}.".casefold()):
            raise ValueError("Mapped IC power pin must belong to the declared component")
        if self.power_net.casefold() == self.return_net.casefold():
            raise ValueError("Mapped IC power and return nets must differ")
        references = tuple(item.reference.casefold() for item in self.capacitors)
        pins = tuple(
            pin.casefold()
            for item in self.capacitors
            for pin in (item.power_pin, item.return_pin)
        )
        if self.ic_reference.casefold() in references:
            raise ValueError("The IC cannot also be a mapped decoupling capacitor")
        if len(set(references)) != len(references):
            raise ValueError("Mapped decoupling capacitor references must be unique")
        if len(set(pins)) != len(pins):
            raise ValueError("Mapped decoupling capacitor pins must be unique")
        return self


class IcDecouplingMap(StrictModel):
    """Exact, source-backed IC decoupling minimums authored by the project."""

    schema_version: Literal["1"] = "1"
    requirements: Annotated[tuple[IcDecouplingRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_requirements_and_components(self) -> IcDecouplingMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("IC decoupling requirement IDs must be unique")
        pins = tuple(
            (item.ic_reference.casefold(), item.power_pin.casefold()) for item in self.requirements
        )
        if len(set(pins)) != len(pins):
            raise ValueError("An IC power pin can appear in only one decoupling requirement")
        capacitor_references = tuple(
            capacitor.reference.casefold()
            for item in self.requirements
            for capacitor in item.capacitors
        )
        if len(set(capacitor_references)) != len(capacitor_references):
            raise ValueError("A decoupling capacitor can appear in only one requirement")
        return self
