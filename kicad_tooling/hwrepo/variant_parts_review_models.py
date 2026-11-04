"""Typed, source-bound purchasing review for one named board variant."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel
from .purchasing_models import PurchasingPlan


class VariantPopulationIssue(StrictModel):
    reference: NonEmptyText
    reason: NonEmptyText


class VariantPartsReviewReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["VARIANT_PARTS_REVIEW"] = "VARIANT_PARTS_REVIEW"
    build_authorized: Literal[False] = False
    purchase_authorized: Literal[False] = False
    project_id: Identifier
    assembly_variant: NonEmptyText
    parts_report: RepositoryPath
    parts_report_sha256: Digest
    findings_view: RepositoryPath
    findings_view_sha256: Digest
    lint_report: RepositoryPath
    lint_report_sha256: Digest
    parts_catalog: RepositoryPath
    parts_catalog_sha256: Digest
    source_hashes: Mapping[RepositoryPath, Digest]
    variant_evidence_sha256: Mapping[RepositoryPath, Digest]
    plan: PurchasingPlan
    unresolved: tuple[VariantPopulationIssue, ...]
    navigation_report: RepositoryPath
    navigation_report_sha256: Digest
    output_directory: str
    artifacts_sha256: Mapping[str, Digest] = Field(default_factory=dict)
