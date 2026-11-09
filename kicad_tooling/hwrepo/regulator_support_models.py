"""Project-authored role maps for active regulator-support components."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Identifier, NonEmptyText, Reference, StrictModel


class RegulatorSupportPinRoleExpectation(StrictModel):
    """Native schematic pin roles explicitly approved for one mapped pin."""

    pin: Reference
    expected_function: NonEmptyText | None = None
    expected_electrical_type: NonEmptyText | None = None


class RegulatorSupportComponentRequirement(StrictModel):
    """Exact identity and complete native pin-role map for an active support device."""

    role: NonEmptyText
    reference: Identifier
    value: NonEmptyText
    symbol: NonEmptyText
    footprint: NonEmptyText
    part_id: Identifier | None = None
    pins: Annotated[tuple[RegulatorSupportPinRoleExpectation, ...], Field(min_length=2)]

    @model_validator(mode="after")
    def complete_unique_pin_map(self) -> RegulatorSupportComponentRequirement:
        prefix = f"{self.reference}.".casefold()
        if any(not item.pin.casefold().startswith(prefix) for item in self.pins):
            raise ValueError("Regulator-support pins must belong to their mapped component")
        if len({item.pin.casefold() for item in self.pins}) != len(self.pins):
            raise ValueError("Regulator-support mapped pins must be unique")
        if not any(
            item.expected_function is not None or item.expected_electrical_type is not None
            for item in self.pins
        ):
            raise ValueError("A support component must declare at least one expected pin role")
        return self


class RegulatorSupportTopologyRequirement(StrictModel):
    """One project-reviewed regulator context and its active support components."""

    id: Identifier
    basis: NonEmptyText
    regulator_reference: Identifier
    components: Annotated[tuple[RegulatorSupportComponentRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_support_components(self) -> RegulatorSupportTopologyRequirement:
        references = (self.regulator_reference, *(item.reference for item in self.components))
        if len({item.casefold() for item in references}) != len(references):
            raise ValueError("Regulator-support component references must be unique")
        if len({item.role.casefold() for item in self.components}) != len(self.components):
            raise ValueError("Regulator-support roles must be unique within a topology")
        return self


class RegulatorSupportPinRoleMap(StrictModel):
    """Explicit active-device role expectations for selected regulator topologies."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[RegulatorSupportTopologyRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_support_topologies(self) -> RegulatorSupportPinRoleMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Regulator-support topology IDs must be unique")
        references = [item.regulator_reference.casefold() for item in self.requirements]
        if len(set(references)) != len(references):
            raise ValueError("A regulator reference can have only one support-role entry")
        return self
