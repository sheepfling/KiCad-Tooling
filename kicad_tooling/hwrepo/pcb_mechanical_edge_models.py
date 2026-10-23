"""Project-owned mechanical board-edge DRC coverage requirements."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Identifier, NonEmptyText, PositiveCount, StrictModel


class PcbMechanicalEdgeClearanceRequirement(StrictModel):
    """Minimum courtyard clearance and exact native rule name for one board side."""

    id: Identifier
    basis: NonEmptyText
    courtyard_layer: Literal["F.Courtyard", "B.Courtyard"]
    rule_name: NonEmptyText
    minimum_clearance_nm: PositiveCount


class PcbMechanicalEdgeClearanceMap(StrictModel):
    """Reviewed mechanical clearance requirement for fitted courtyard geometry."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbMechanicalEdgeClearanceRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_native_rules(self) -> PcbMechanicalEdgeClearanceMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Mechanical edge-clearance requirement IDs must be unique")
        if len({item.rule_name.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Mechanical edge-clearance native rule names must be unique")
        if len({item.courtyard_layer for item in self.requirements}) != len(self.requirements):
            raise ValueError(
                "Mechanical edge-clearance map may declare one rule per courtyard side"
            )
        return self
