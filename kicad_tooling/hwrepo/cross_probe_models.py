"""Typed navigation evidence between a parts plan and verified design drawings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .findings_view_models import ReviewDrawing
from .model_primitives import Digest, FiniteMeasure, Identifier, RepositoryPath, StrictModel


class CrossProbeLocation(StrictModel):
    kind: Literal["pcb", "schematic"]
    source_path: RepositoryPath
    x_mm: FiniteMeasure
    y_mm: FiniteMeasure
    drawing_file: str | None = None
    sheet_instance_path: str | None = None
    sheet_path: tuple[str, ...] = ()
    side: Literal["F.Cu", "B.Cu"] | None = None
    symbol_uuid: str | None = None


class CrossProbeEntry(StrictModel):
    reference: Identifier
    part_id: str | None = None
    value: str
    footprint: str
    population: Literal["FITTED", "DNP", "EXCLUDED", "DUPLICATE"]
    board: tuple[CrossProbeLocation, ...] = ()
    schematic: tuple[CrossProbeLocation, ...] = ()
    issues: tuple[str, ...] = ()


class CrossProbeReport(StrictModel):
    """Source-matched navigation aid, never a part or footprint approval."""

    schema_version: Literal["1"] = "1"
    lane: Literal["BOM_DESIGN_CROSS_PROBE"] = "BOM_DESIGN_CROSS_PROBE"
    build_authorized: Literal[False] = False
    purchase_authorized: Literal[False] = False
    project_id: Identifier
    parts_report: RepositoryPath
    parts_report_sha256: Digest
    findings_view: RepositoryPath
    findings_view_sha256: Digest
    source_hashes: Mapping[RepositoryPath, Digest]
    variant_scope: Literal["NOT_RECORDED"] = "NOT_RECORDED"
    entries: tuple[CrossProbeEntry, ...]
    drawings: tuple[ReviewDrawing, ...] = ()
    issues: tuple[str, ...] = ()
    output_directory: str
    artifacts_sha256: Mapping[str, Digest] = Field(default_factory=dict)
