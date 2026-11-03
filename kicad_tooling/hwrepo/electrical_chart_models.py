"""Typed receipts for saved simulation charts and AC run comparisons."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field

from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel


class ElectricalChartCase(StrictModel):
    """One chart and numeric export derived from a retained simulation case."""

    id: Identifier
    status: Literal["PASS", "SKIPPED", "FAIL"]
    samples: Annotated[int, Field(ge=0)] = 0
    waveform_sha256: Digest | None = None
    csv: RepositoryPath | None = None
    png: RepositoryPath | None = None
    svg: RepositoryPath | None = None
    html: RepositoryPath | None = None
    detail: NonEmptyText


class ElectricalChartsReport(StrictModel):
    """Chart output remains secondary evidence bound to an analysis receipt."""

    schema_version: Literal["1"] = "1"
    lane: Literal["ELECTRICAL_CHARTS"] = "ELECTRICAL_CHARTS"
    build_authorized: Literal[False] = False
    project_id: Identifier
    status: Literal["PASS", "PARTIAL", "FAIL"]
    source_analysis_status: Literal["PASS", "FAIL", "NOT_CONFIGURED"]
    source_receipt: NonEmptyText
    source_report_sha256: Digest
    run_directory: NonEmptyText
    cases: tuple[ElectricalChartCase, ...]
    viewer_index: RepositoryPath | None = None
    grounding_csv: RepositoryPath | None = None
    power_csv: RepositoryPath | None = None
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    next_actions: tuple[NonEmptyText, ...] = ()


class ElectricalChartsSuiteReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["ELECTRICAL_CHARTS_SUITE"] = "ELECTRICAL_CHARTS_SUITE"
    status: Literal["PASS", "PARTIAL", "FAIL"]
    run_directory: NonEmptyText
    reports: tuple[ElectricalChartsReport, ...]


class AcComparisonRun(StrictModel):
    """Exact saved evidence used for one side of an AC overlay."""

    receipt: RepositoryPath
    report_sha256: Digest
    requirements_sha256: Digest
    waveform_sha256: Digest
    analysis_status: Literal["PASS", "FAIL", "NOT_CONFIGURED"]
    input_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    samples: Annotated[int, Field(ge=2)]
    first_hz: float
    last_hz: float
    window_start_hz: float
    window_stop_hz: float


class AcComparisonReport(StrictModel):
    """Two saved AC runs shown together without inferred acceptance."""

    schema_version: Literal["1"] = "1"
    lane: Literal["ELECTRICAL_AC_COMPARISON"] = "ELECTRICAL_AC_COMPARISON"
    build_authorized: Literal[False] = False
    physical_validated: Literal[False] = False
    status: Literal["READY_FOR_REVIEW"] = "READY_FOR_REVIEW"
    project_id: Identifier
    case_id: Identifier
    measure_id: Identifier
    expression: NonEmptyText
    unit: NonEmptyText
    quantity_kind: Literal["SCALAR", "DERIVED_MAGNITUDE"]
    baseline: AcComparisonRun
    candidate: AcComparisonRun
    overlap: Literal["OVERLAP", "DISJOINT"]
    display_points_baseline: Annotated[int, Field(ge=2)]
    display_points_candidate: Annotated[int, Field(ge=2)]
    output_directory: NonEmptyText
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
