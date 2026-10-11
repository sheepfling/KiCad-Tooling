"""Typed source-bound PCB component inventory coverage records."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel


class PcbMissingFootprintPlacement(StrictModel):
    """A fitted schematic reference with an assigned footprint absent from the PCB."""

    reference: Identifier
    assigned_footprint: NonEmptyText


class PcbFootprintIdentityMismatch(StrictModel):
    """A schematic-assigned footprint identity differs from its native board placement."""

    reference: Identifier
    assigned_footprint: NonEmptyText
    placed_footprint: NonEmptyText


class PcbComponentInventoryComparison(StrictModel):
    """Deterministic comparison results for fitted schematic component placements."""

    missing_placements: tuple[PcbMissingFootprintPlacement, ...] = ()
    footprint_mismatches: tuple[PcbFootprintIdentityMismatch, ...] = ()

    @model_validator(mode="after")
    def unique_references(self) -> PcbComponentInventoryComparison:
        references = [
            item.reference.casefold()
            for item in (*self.missing_placements, *self.footprint_mismatches)
        ]
        if len(references) != len(set(references)):
            raise ValueError("PCB component inventory comparison references must be unique")
        return self


class PcbComponentInventoryCoverageReport(StrictModel):
    """Native source receipt and schematic-to-board inventory candidates."""

    status: Literal["NOT_APPLICABLE", "COMPLETE", "BLOCKED", "DISABLED"] = "NOT_APPLICABLE"
    mode: Literal["review", "block", "off"] | None = None
    netlist_sha256: Digest | None = None
    board_path: RepositoryPath | None = None
    board_sha256: Digest | None = None
    snapshot_path: RepositoryPath | None = None
    snapshot_sha256: Digest | None = None
    snapshot_schema: Literal["12"] | None = None
    kicad_version: NonEmptyText | None = None
    image: NonEmptyText | None = None
    probe_sha256: Digest | None = None
    missing_placements: tuple[PcbMissingFootprintPlacement, ...] = ()
    footprint_mismatches: tuple[PcbFootprintIdentityMismatch, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def consistent_source_receipt(self) -> PcbComponentInventoryCoverageReport:
        references = [
            item.reference.casefold()
            for item in (*self.missing_placements, *self.footprint_mismatches)
        ]
        if len(references) != len(set(references)):
            raise ValueError("PCB component inventory finding references must be unique")
        if self.status == "COMPLETE":
            if any(
                value is None
                for value in (
                    self.mode,
                    self.netlist_sha256,
                    self.board_path,
                    self.board_sha256,
                    self.snapshot_path,
                    self.snapshot_sha256,
                    self.snapshot_schema,
                    self.kicad_version,
                    self.image,
                    self.probe_sha256,
                )
            ):
                raise ValueError("Complete PCB component inventory needs a full source receipt")
            if self.mode == "off":
                raise ValueError("Disabled PCB component inventory cannot be complete")
            if self.issue is not None:
                raise ValueError("Complete PCB component inventory cannot include an issue")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked PCB component inventory must explain the evidence gap")
        if self.status != "COMPLETE" and (self.missing_placements or self.footprint_mismatches):
            raise ValueError("Only complete PCB component inventory can report comparison findings")
        return self
