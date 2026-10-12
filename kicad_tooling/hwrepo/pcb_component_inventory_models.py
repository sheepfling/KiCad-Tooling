"""Typed source-bound PCB component inventory coverage records."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel
from .pcb_pad_net_models import PcbSchematicBoardPadNetMismatch


class PcbMissingFootprintPlacement(StrictModel):
    """A fitted schematic reference with an assigned footprint absent from the PCB."""

    reference: Identifier
    assigned_footprint: NonEmptyText


class PcbFootprintIdentityMismatch(StrictModel):
    """A schematic-assigned footprint identity differs from its native board placement."""

    reference: Identifier
    assigned_footprint: NonEmptyText
    placed_footprint: NonEmptyText


class PcbPopulationMismatch(StrictModel):
    """Schematic and placed PCB footprint disagree on DNP population state."""

    reference: Identifier
    schematic_dnp: bool
    board_dnp: bool


class PcbComponentValueMismatch(StrictModel):
    """Schematic and placed PCB value fields differ for one fitted component."""

    reference: Identifier
    schematic_value: NonEmptyText
    board_value: str


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
    snapshot_schema: Literal["12", "13"] | None = None
    kicad_version: NonEmptyText | None = None
    image: NonEmptyText | None = None
    probe_sha256: Digest | None = None
    missing_placements: tuple[PcbMissingFootprintPlacement, ...] = ()
    footprint_mismatches: tuple[PcbFootprintIdentityMismatch, ...] = ()
    population_mismatches: tuple[PcbPopulationMismatch, ...] = ()
    value_comparison_status: Literal["NOT_APPLICABLE", "COMPLETE", "BLOCKED", "DISABLED"] = (
        "NOT_APPLICABLE"
    )
    value_mismatches: tuple[PcbComponentValueMismatch, ...] = ()
    value_comparison_issue: NonEmptyText | None = None
    pad_net_comparison_status: Literal["NOT_APPLICABLE", "COMPLETE", "BLOCKED", "DISABLED"] = (
        "NOT_APPLICABLE"
    )
    pad_net_mismatches: tuple[PcbSchematicBoardPadNetMismatch, ...] = ()
    pad_net_comparison_issue: NonEmptyText | None = None
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def consistent_source_receipt(self) -> PcbComponentInventoryCoverageReport:
        references = [
            item.reference.casefold()
            for item in (*self.missing_placements, *self.footprint_mismatches)
        ]
        if len(references) != len(set(references)):
            raise ValueError("PCB component inventory finding references must be unique")
        population_references = [item.reference.casefold() for item in self.population_mismatches]
        if len(population_references) != len(set(population_references)):
            raise ValueError("PCB population mismatch references must be unique")
        value_references = [item.reference.casefold() for item in self.value_mismatches]
        if len(value_references) != len(set(value_references)):
            raise ValueError("PCB value mismatch references must be unique")
        if self.value_comparison_status == "COMPLETE" and self.snapshot_schema != "13":
            raise ValueError("Complete PCB value comparison requires snapshot schema 13")
        if self.value_comparison_status == "BLOCKED" and self.value_comparison_issue is None:
            raise ValueError("Blocked PCB value comparison must explain the evidence gap")
        if self.value_comparison_status != "BLOCKED" and self.value_comparison_issue is not None:
            raise ValueError("Only blocked PCB value comparison may include an issue")
        if self.value_comparison_status != "COMPLETE" and self.value_mismatches:
            raise ValueError("Only complete PCB value comparison can report mismatch rows")
        pad_keys = [(item.reference.casefold(), item.pin) for item in self.pad_net_mismatches]
        if len(pad_keys) != len(set(pad_keys)):
            raise ValueError("PCB pad net mismatch pins must be unique")
        if self.pad_net_comparison_status == "BLOCKED" and self.pad_net_comparison_issue is None:
            raise ValueError("Blocked PCB pad net comparison must explain the evidence gap")
        if (
            self.pad_net_comparison_status != "BLOCKED"
            and self.pad_net_comparison_issue is not None
        ):
            raise ValueError("Only blocked PCB pad net comparison may include an issue")
        if self.pad_net_comparison_status != "COMPLETE" and self.pad_net_mismatches:
            raise ValueError("Only complete PCB pad net comparison can report mismatch rows")
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
        if self.status != "COMPLETE" and (
            self.missing_placements
            or self.footprint_mismatches
            or self.population_mismatches
            or self.value_comparison_status == "COMPLETE"
            or self.pad_net_comparison_status == "COMPLETE"
        ):
            raise ValueError("Only complete PCB component inventory can report comparison findings")
        return self
