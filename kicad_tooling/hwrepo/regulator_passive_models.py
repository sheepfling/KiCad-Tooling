"""Project-authored regulator and required-passive topology maps."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, Reference, StrictModel


class RegulatorPassivePinRequirement(StrictModel):
    """One exact component pin; a missing net value explicitly requires no assignment."""

    pin: Reference
    net: NetName | None = None


class RegulatorPassiveComponentRequirement(StrictModel):
    """Exact schematic identity and complete pin-to-net map for one component."""

    reference: Identifier
    value: NonEmptyText
    symbol: NonEmptyText
    footprint: NonEmptyText
    part_id: Identifier | None = None
    pins: Annotated[tuple[RegulatorPassivePinRequirement, ...], Field(min_length=2)]

    @model_validator(mode="after")
    def complete_unique_pin_map(self) -> RegulatorPassiveComponentRequirement:
        prefix = f"{self.reference}.".casefold()
        if any(not item.pin.casefold().startswith(prefix) for item in self.pins):
            raise ValueError("Regulator passive-map pins must belong to their component")
        if len({item.pin.casefold() for item in self.pins}) != len(self.pins):
            raise ValueError("Regulator passive-map pins must be unique")
        return self


class RegulatorRequiredPassive(StrictModel):
    """One source-backed passive role and its expected exact component map."""

    role: Identifier
    component: RegulatorPassiveComponentRequirement


class RegulatorPassiveTopologyAlternative(StrictModel):
    """One explicitly approved alternative passive set for the same regulator."""

    id: Identifier
    basis: NonEmptyText
    required_passives: Annotated[tuple[RegulatorRequiredPassive, ...], Field(min_length=1)]


class RegulatorPassiveTopologyRequirement(StrictModel):
    """One regulator application topology required by project-reviewed evidence."""

    id: Identifier
    basis: NonEmptyText
    regulator: RegulatorPassiveComponentRequirement
    required_passives: Annotated[tuple[RegulatorRequiredPassive, ...], Field(min_length=1)]
    approved_alternatives: tuple[RegulatorPassiveTopologyAlternative, ...] = ()

    @model_validator(mode="after")
    def unique_topology_components(self) -> RegulatorPassiveTopologyRequirement:
        variants = (
            (self.id, self.required_passives),
            *((item.id, item.required_passives) for item in self.approved_alternatives),
        )
        if len({item[0].casefold() for item in variants}) != len(variants):
            raise ValueError("Regulator passive topology variant IDs must be unique")
        for _, passives in variants:
            references = (
                self.regulator.reference,
                *(item.component.reference for item in passives),
            )
            if len({item.casefold() for item in references}) != len(references):
                raise ValueError("Regulator passive topology component references must be unique")
        return self


class RegulatorPassiveTopologyMap(StrictModel):
    """Exact approved regulator-support topologies for one design-lint policy."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[RegulatorPassiveTopologyRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_regulator_requirements(self) -> RegulatorPassiveTopologyMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Regulator passive topology IDs must be unique")
        references = [item.regulator.reference.casefold() for item in self.requirements]
        if len(set(references)) != len(references):
            raise ValueError("A regulator reference can have only one passive topology entry")
        return self
