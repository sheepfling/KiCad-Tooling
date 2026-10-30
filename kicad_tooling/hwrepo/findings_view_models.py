"""Typed, source-bound visual review records."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .contracts import model_json_bytes
from .model_primitives import (
    Digest,
    FiniteMeasure,
    Identifier,
    NonEmptyText,
    RepositoryPath,
    StrictModel,
)


class FindingMarker(StrictModel):
    drawing: Literal["schematic", "pcb"]
    x_mm: FiniteMeasure
    y_mm: FiniteMeasure
    detail: str = ""
    drawing_file: RepositoryPath | None = None
    sheet_instance_path: NonEmptyText | None = None


class ReviewFinding(StrictModel):
    origin: Literal["ERC", "DRC", "DESIGN_LINT"]
    rule: NonEmptyText
    severity: NonEmptyText
    title: NonEmptyText
    description: str = ""
    fingerprint: Digest | None = None
    evidence: Mapping[str, tuple[str, ...]] = Field(default_factory=dict)
    markers: tuple[FindingMarker, ...] = ()
    unmapped_reason: str | None = None


def finding_fingerprint(finding: ReviewFinding) -> str:
    """Use the explicit finding identity or its stable typed payload digest."""
    return finding.fingerprint or hashlib.sha256(model_json_bytes(finding)).hexdigest()


class ReviewDrawing(StrictModel):
    kind: Literal["schematic", "pcb"]
    file: str
    source_artifact: str
    sha256: Digest
    width_mm: FiniteMeasure
    height_mm: FiniteMeasure
    mapping_supported: bool
    sheet_instance_path: NonEmptyText | None = None
    sheet_path: tuple[NonEmptyText, ...] = ()
    schematic_source: RepositoryPath | None = None
    schematic_source_sha256: Digest | None = None


class FindingsViewReport(StrictModel):
    """A review artifact, not a design approval or a new check outcome."""

    schema_version: Literal["1"] = "1"
    lane: Literal["FINDINGS_VIEW"] = "FINDINGS_VIEW"
    project_id: Identifier
    native_status: Literal["PASS", "FAIL"]
    lint_status: Literal["NOT_SUPPLIED", "PASS", "REVIEW", "FAIL", "BLOCKED"]
    native_summary: str
    native_summary_sha256: Digest
    lint_report: str | None = None
    lint_report_sha256: Digest | None = None
    source_hashes: Mapping[str, Digest]
    drawings: tuple[ReviewDrawing, ...] = ()
    findings: tuple[ReviewFinding, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    output_directory: str
    artifacts_sha256: Mapping[str, Digest] = Field(default_factory=dict)
    build_authorized: Literal[False] = False
