"""Typed source-bound PCB component inventory coverage records."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel
from .pcb_board_only_footprint_models import PcbBoardOnlyFootprintCoverage
from .pcb_pad_net_models import PcbSchematicBoardPadNetMismatch
from .pcb_required_fitted_reference_models import PcbRequiredFittedReferenceCoverage


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
    variant: NonEmptyText | None = None


class PcbVariantPopulationEvidence(StrictModel):
    """Source-bound KiCad exports used for one named variant's DNP comparison."""

    variant: NonEmptyText
    netlist_path: RepositoryPath
    netlist_sha256: Digest
    netlist_command_path: RepositoryPath
    netlist_command_sha256: Digest
    board_all_positions_path: RepositoryPath
    board_all_positions_sha256: Digest
    board_all_command_path: RepositoryPath
    board_all_command_sha256: Digest
    board_fitted_positions_path: RepositoryPath
    board_fitted_positions_sha256: Digest
    board_fitted_command_path: RepositoryPath
    board_fitted_command_sha256: Digest


class PcbVariantPopulationCoverage(StrictModel):
    """Coverage state for named schematic/PCB population variants."""

    status: Literal["NOT_APPLICABLE", "COMPLETE", "BLOCKED", "DISABLED"] = "NOT_APPLICABLE"
    project_path: RepositoryPath | None = None
    project_sha256: Digest | None = None
    schematic_path: RepositoryPath | None = None
    schematic_sha256: Digest | None = None
    board_path: RepositoryPath | None = None
    board_sha256: Digest | None = None
    kicad_version: NonEmptyText | None = None
    image: NonEmptyText | None = None
    board_variant_probe_path: RepositoryPath | None = None
    board_variant_probe_sha256: Digest | None = None
    board_variant_request_path: RepositoryPath | None = None
    board_variant_request_sha256: Digest | None = None
    board_variant_command_path: RepositoryPath | None = None
    board_variant_command_sha256: Digest | None = None
    evidence: tuple[PcbVariantPopulationEvidence, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def consistent_variant_coverage(self) -> PcbVariantPopulationCoverage:
        variants = [item.variant.casefold() for item in self.evidence]
        if len(variants) != len(set(variants)):
            raise ValueError("Variant population evidence must contain unique variant names")
        if self.status == "COMPLETE":
            if not self.evidence or self.issue is not None:
                raise ValueError("Complete variant population coverage needs evidence and no issue")
            if any(
                value is None
                for value in (
                    self.project_path,
                    self.project_sha256,
                    self.schematic_path,
                    self.schematic_sha256,
                    self.board_path,
                    self.board_sha256,
                    self.kicad_version,
                    self.image,
                    self.board_variant_probe_path,
                    self.board_variant_probe_sha256,
                    self.board_variant_request_path,
                    self.board_variant_request_sha256,
                    self.board_variant_command_path,
                    self.board_variant_command_sha256,
                )
            ):
                raise ValueError(
                    "Complete variant population coverage needs source and tool identity"
                )
        elif self.status == "BLOCKED":
            if self.issue is None:
                raise ValueError(
                    "Blocked variant population coverage must explain the evidence gap"
                )
        elif self.issue is not None or self.evidence:
            raise ValueError(
                "Inactive variant population coverage cannot contain evidence or an issue"
            )
        return self


class PcbComponentValueMismatch(StrictModel):
    """Schematic and placed PCB value fields differ for one fitted component."""

    reference: Identifier
    schematic_value: NonEmptyText
    board_value: str
    variant: NonEmptyText | None = None


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
    snapshot_schema: Literal["12", "13", "14", "15"] | None = None
    kicad_version: NonEmptyText | None = None
    image: NonEmptyText | None = None
    probe_sha256: Digest | None = None
    missing_placements: tuple[PcbMissingFootprintPlacement, ...] = ()
    footprint_mismatches: tuple[PcbFootprintIdentityMismatch, ...] = ()
    population_mismatches: tuple[PcbPopulationMismatch, ...] = ()
    variant_population: PcbVariantPopulationCoverage = Field(
        default_factory=PcbVariantPopulationCoverage
    )
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
    board_only_footprint_coverage: PcbBoardOnlyFootprintCoverage = Field(
        default_factory=PcbBoardOnlyFootprintCoverage
    )
    required_fitted_reference_coverage: PcbRequiredFittedReferenceCoverage = Field(
        default_factory=PcbRequiredFittedReferenceCoverage
    )
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def consistent_source_receipt(self) -> PcbComponentInventoryCoverageReport:
        references = [
            item.reference.casefold()
            for item in (*self.missing_placements, *self.footprint_mismatches)
        ]
        if len(references) != len(set(references)):
            raise ValueError("PCB component inventory finding references must be unique")
        population_keys = [
            (item.variant.casefold() if item.variant is not None else "", item.reference.casefold())
            for item in self.population_mismatches
        ]
        if len(population_keys) != len(set(population_keys)):
            raise ValueError("PCB population mismatch references must be unique")
        value_references = [
            (item.variant.casefold() if item.variant is not None else "", item.reference.casefold())
            for item in self.value_mismatches
        ]
        if len(value_references) != len(set(value_references)):
            raise ValueError("PCB value mismatch references must be unique")
        if self.value_comparison_status == "COMPLETE" and self.snapshot_schema not in {
            "13",
            "14",
            "15",
        }:
            raise ValueError("Complete PCB value comparison requires snapshot schema 13 or later")
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
        if self.board_only_footprint_coverage.status == "COMPLETE" and (
            self.status != "COMPLETE" or self.snapshot_schema not in {"12", "13", "14", "15"}
        ):
            raise ValueError("Complete board-only coverage needs complete source-bound inventory")
        if self.board_only_footprint_coverage.status == "BLOCKED" and self.status != "BLOCKED":
            raise ValueError("Blocked board-only coverage must block PCB inventory coverage")
        required_fitted = self.required_fitted_reference_coverage
        if required_fitted.status == "COMPLETE" and (
            self.status != "COMPLETE" or self.snapshot_schema not in {"12", "13", "14", "15"}
        ):
            raise ValueError("Complete required-fitted coverage needs complete native inventory")
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
            or self.board_only_footprint_coverage.status == "COMPLETE"
        ):
            raise ValueError("Only complete PCB component inventory can report comparison findings")
        return self
