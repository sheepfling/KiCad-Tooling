"""Explicit source and coordinate-frame contract for visual assembly review."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    FiniteMeasure,
    Identifier,
    NonEmptyText,
    RepositoryPath,
    StrictModel,
)


class AssemblyPlacement(StrictModel):
    """Rigid enclosure-model to board-model transform, with translation in mm."""

    source_frame: NonEmptyText
    target_frame: NonEmptyText
    translation_mm: tuple[FiniteMeasure, FiniteMeasure, FiniteMeasure]
    rotation_xyzw: tuple[FiniteMeasure, FiniteMeasure, FiniteMeasure, FiniteMeasure]

    @model_validator(mode="after")
    def valid_rotation(self) -> AssemblyPlacement:
        norm = sum(value * value for value in self.rotation_xyzw)
        if not math.isclose(norm, 1.0, abs_tol=1e-6):
            raise ValueError("Placement quaternion must be normalized")
        return self


class AssemblyPlacementContract(StrictModel):
    """Project-authored identity and placement for one board and adjacent model."""

    schema_version: Literal["1"] = "1"
    project_id: Identifier
    board_glb_sha256: Digest
    board_frame: NonEmptyText
    board_unit: Literal["mm", "m"]
    enclosure_model: RepositoryPath
    enclosure_sha256: Digest
    enclosure_frame: NonEmptyText
    enclosure_unit: Literal["mm", "m"]
    placement: AssemblyPlacement | None = None

    @model_validator(mode="after")
    def distinct_frames(self) -> AssemblyPlacementContract:
        if self.board_frame == self.enclosure_frame:
            raise ValueError("Board and enclosure model frames must be distinct")
        if self.placement is not None and (
            self.placement.source_frame != self.enclosure_frame
            or self.placement.target_frame != self.board_frame
        ):
            raise ValueError("Placement source/target frames differ from model frames")
        return self


class AssemblyReviewReport(StrictModel):
    """Visual overlay evidence; no physical clearance or fit conclusion."""

    schema_version: Literal["1"] = "1"
    lane: Literal["MECHANICAL_ASSEMBLY_REVIEW"] = "MECHANICAL_ASSEMBLY_REVIEW"
    build_authorized: Literal[False] = False
    fit_certified: Literal[False] = False
    interference_assessed: Literal[False] = False
    clearance_assessed: Literal[False] = False
    project_id: Identifier
    status: Literal["READY", "REVIEW", "INCOMPLETE"]
    board_receipt: RepositoryPath
    board_receipt_sha256: Digest
    placement_contract: RepositoryPath
    placement_contract_sha256: Digest
    board_glb_sha256: Digest
    enclosure_model: RepositoryPath
    enclosure_expected_sha256: Digest
    enclosure_sha256: Digest | None = None
    board_frame: NonEmptyText
    board_unit: Literal["mm", "m"]
    enclosure_frame: NonEmptyText
    enclosure_unit: Literal["mm", "m"]
    placement: AssemblyPlacement | None = None
    source_hashes: Mapping[RepositoryPath, Digest]
    model_status: str
    assembly_variant: str | None = None
    issues: tuple[str, ...] = ()
    output_directory: str
    artifacts_sha256: Mapping[str, Digest] = Field(default_factory=dict)
