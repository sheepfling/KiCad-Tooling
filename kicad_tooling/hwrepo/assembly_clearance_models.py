"""Authored free-space envelope and measured board-mesh margin evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    FiniteMeasure,
    Identifier,
    NonEmptyText,
    NonNegativeMeasure,
    RepositoryPath,
    StrictModel,
)


class AssemblyFreeSpaceBox(StrictModel):
    """A reviewed rectangular free-space region in the enclosure model frame."""

    lower: tuple[FiniteMeasure, FiniteMeasure, FiniteMeasure]
    upper: tuple[FiniteMeasure, FiniteMeasure, FiniteMeasure]
    basis: NonEmptyText

    @model_validator(mode="after")
    def positive_extent(self) -> AssemblyFreeSpaceBox:
        if any(high <= low for low, high in zip(self.lower, self.upper, strict=True)):
            raise ValueError("Free-space box upper bounds must exceed lower bounds")
        return self


class AssemblyClearanceContract(StrictModel):
    """Project-owned reviewed envelope, bound to one exact placement contract."""

    schema_version: Literal["1"] = "1"
    project_id: Identifier
    placement_contract_sha256: Digest
    free_space: AssemblyFreeSpaceBox
    required_margin_mm: NonNegativeMeasure


class AssemblyClearanceReport(StrictModel):
    """Box margins and surface gap; solid enclosure fit remains unassessed."""

    schema_version: Literal["1"] = "1"
    lane: Literal["MECHANICAL_BOX_CLEARANCE"] = "MECHANICAL_BOX_CLEARANCE"
    build_authorized: Literal[False] = False
    fit_certified: Literal[False] = False
    enclosure_mesh_clearance_assessed: Literal[False] = False
    project_id: Identifier
    status: Literal[
        "CLEAR_WITHIN_BOX",
        "LOW_CLEARANCE",
        "BOX_INTERFERENCE",
        "MESH_SURFACE_INTERSECTION",
        "LOW_SURFACE_GAP",
        "UNASSESSED",
    ]
    assembly_review: RepositoryPath
    assembly_review_sha256: Digest
    clearance_contract: RepositoryPath
    clearance_contract_sha256: Digest
    placement_contract: RepositoryPath
    placement_contract_sha256: Digest
    board_glb_sha256: Digest
    enclosure_glb_sha256: Digest | None = None
    source_hashes: Mapping[RepositoryPath, Digest]
    free_space: AssemblyFreeSpaceBox
    required_margin_mm: NonNegativeMeasure
    face_margins_mm: Mapping[str, FiniteMeasure] = Field(default_factory=dict)
    minimum_margin_mm: FiniteMeasure | None = None
    referenced_vertices: int = 0
    surface_status: Literal["INTERSECTING", "SEPARATED", "UNASSESSED"] = "UNASSESSED"
    surface_gap_mm: NonNegativeMeasure | None = None
    board_triangles: int = 0
    enclosure_triangles: int = 0
    surface_pairs_tested: int = 0
    first_surface_intersection: tuple[int, int] | None = None
    issues: tuple[NonEmptyText, ...] = ()
    output_directory: str
    artifacts_sha256: Mapping[str, Digest] = Field(default_factory=dict)
