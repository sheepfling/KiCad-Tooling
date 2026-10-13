"""Project-authored requirements for references that must be fitted on a PCB."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Digest, Identifier, NonEmptyText, NonNegativeCount, StrictModel


class PcbRequiredFittedReference(StrictModel):
    """One independently reviewed component reference required in the base assembly."""

    reference: Identifier
    footprint: NonEmptyText
    basis: NonEmptyText
    symbol: NonEmptyText | None = None
    part_id: Identifier | None = None


class PcbRequiredFittedReferenceMap(StrictModel):
    """Project-owned list of exact PCB component identities that must be fitted."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbRequiredFittedReference, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_references(self) -> PcbRequiredFittedReferenceMap:
        references = tuple(item.reference.casefold() for item in self.requirements)
        if len(set(references)) != len(references):
            raise ValueError("Required fitted PCB references must be unique case-insensitively")
        return self


PcbRequiredFittedReferenceViolation = Literal[
    "schematic_reference_missing",
    "schematic_component_dnp",
    "schematic_footprint_unassigned",
    "schematic_footprint_mismatch",
    "schematic_symbol_missing",
    "schematic_symbol_mismatch",
    "schematic_part_id_mismatch",
    "board_footprint_missing",
    "board_footprint_dnp",
    "board_footprint_mismatch",
]


class PcbRequiredFittedReferenceMismatch(StrictModel):
    """One required-reference record that does not satisfy its fitted identity."""

    reference: Identifier
    basis: NonEmptyText
    expected_footprint: NonEmptyText
    expected_symbol: NonEmptyText | None = None
    observed_symbol: str | None = None
    expected_part_id: Identifier | None = None
    observed_part_id: Identifier | None = None
    schematic_footprint: str | None = None
    board_footprint: NonEmptyText | None = None
    schematic_dnp: bool | None = None
    board_dnp: bool | None = None
    violations: Annotated[tuple[PcbRequiredFittedReferenceViolation, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_violations(self) -> PcbRequiredFittedReferenceMismatch:
        if len(set(self.violations)) != len(self.violations):
            raise ValueError("Required fitted PCB violations must be unique")
        return self


class PcbRequiredFittedReferenceCoverage(StrictModel):
    """Evidence state and mismatches for a project-authored fitted-reference map."""

    status: Literal["COMPLETE", "BLOCKED", "DISABLED"] = "DISABLED"
    mode: Literal["review", "block", "off"] = "off"
    map_sha256: Digest | None = None
    requirement_count: NonNegativeCount = 0
    mismatches: tuple[PcbRequiredFittedReferenceMismatch, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def consistent_coverage(self) -> PcbRequiredFittedReferenceCoverage:
        references = tuple(item.reference.casefold() for item in self.mismatches)
        if len(set(references)) != len(references):
            raise ValueError("Required fitted PCB mismatch references must be unique")
        if self.status == "COMPLETE":
            if (
                self.mode == "off"
                or self.map_sha256 is None
                or self.requirement_count == 0
                or self.issue is not None
                or len(self.mismatches) > self.requirement_count
            ):
                raise ValueError("Complete required fitted PCB coverage needs valid map evidence")
        elif self.status == "BLOCKED":
            if self.mode == "off" or self.issue is None or self.mismatches:
                raise ValueError(
                    "Blocked required fitted PCB coverage needs an active mode and issue"
                )
        elif (
            self.mode != "off"
            or self.map_sha256 is not None
            or self.requirement_count != 0
            or self.mismatches
            or self.issue is not None
        ):
            raise ValueError("Disabled required fitted PCB coverage cannot contain evidence")
        return self
