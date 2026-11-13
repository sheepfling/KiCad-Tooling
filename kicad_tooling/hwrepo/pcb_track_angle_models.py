"""Project-authored per-net track-angle requirements."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, StrictModel

AngleDegrees = Annotated[int, Field(strict=True, ge=0, le=180)]


class PcbTrackAngleRequirement(StrictModel):
    """One reviewed net scope and its inclusive KiCad track-angle bounds."""

    id: Identifier
    basis: NonEmptyText
    net: NetName
    rule_name: NonEmptyText
    minimum_degrees: AngleDegrees | None = None
    maximum_degrees: AngleDegrees | None = None

    @model_validator(mode="after")
    def valid_native_selector(self) -> PcbTrackAngleRequirement:
        if self.minimum_degrees is None and self.maximum_degrees is None:
            raise ValueError("A PCB track-angle requirement needs at least one degree bound")
        if (
            self.minimum_degrees is not None
            and self.maximum_degrees is not None
            and self.minimum_degrees > self.maximum_degrees
        ):
            raise ValueError("A PCB track-angle minimum cannot exceed its maximum")
        if any(character in "'\\\"" or ord(character) < 32 for character in self.net):
            raise ValueError("PCB track-angle net cannot be represented by an exact native rule")
        return self


class PcbTrackAngleMap(StrictModel):
    """Explicit project-selected per-net angle limits for custom DRC coverage."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbTrackAngleRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_scopes(self) -> PcbTrackAngleMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("PCB track-angle requirement IDs must be unique")
        if len({item.rule_name.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("PCB track-angle rule names must be unique")
        if len({item.net.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("A PCB net can appear in only one track-angle requirement")
        return self
