"""Authored release policy, manifest, and evidence-reference contracts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from enum import Enum
from typing import Literal

from pydantic import Field

from .model_primitives import (
    Digest,
    GitCommit,
    Identifier,
    NonEmptyText,
    RepositoryPath,
    StrictModel,
)
from .product_models import Assurance
from .release_model_types import ReleaseClass


class ReleaseAssurancePolicy(StrictModel):
    release_class: ReleaseClass
    minimum_assurance: Assurance


class ReleasePoliciesCatalog(StrictModel):
    schema_version: Literal["1"] = "1"
    policies: tuple[ReleaseAssurancePolicy, ...]


class ReleaseStatus(str, Enum):
    CANDIDATE = "candidate"
    APPROVED = "approved"


class DeviationStatus(str, Enum):
    OPEN = "open"
    APPROVED = "approved"
    CLOSED = "closed"


class ReleaseVariant(StrictModel):
    product: Identifier
    product_revision: Identifier
    variant: Identifier
    variant_revision: Identifier


class ReleaseLibrary(StrictModel):
    id: Identifier
    version: NonEmptyText
    provenance_sha256: Digest
    licensing_sha256: Digest


class ReleaseInterface(StrictModel):
    id: Identifier
    revision: NonEmptyText


class ReleaseArtifactKind(str, Enum):
    REVIEW_RECORD = "review_record"
    BOM = "bom"
    SCHEMATIC_EXPORT = "schematic_export"
    PCB_EXPORT = "pcb_export"
    HARNESS_EXPORT = "harness_export"
    VALIDATION_REPORT = "validation_report"
    FABRICATION_PACKAGE = "fabrication_package"
    ASSEMBLY_PACKAGE = "assembly_package"


class ReleaseArtifact(StrictModel):
    id: Identifier
    kind: ReleaseArtifactKind
    path: RepositoryPath
    sha256: Digest
    intended_use: NonEmptyText


class ReleaseDeviation(StrictModel):
    id: Identifier
    scope: tuple[Identifier, ...]
    owner: NonEmptyText
    reason: NonEmptyText
    status: DeviationStatus
    expires: date
    evidence: tuple[Identifier, ...]


class ReleaseApproval(StrictModel):
    electrical_reviewer: NonEmptyText
    mechanical_reviewer: NonEmptyText | None = None
    integrator: NonEmptyText
    release_authority: NonEmptyText | None = None
    approved_at: date
    evidence: tuple[Identifier, ...]


class EvidenceFile(StrictModel):
    path: RepositoryPath
    sha256: Digest


class ReleaseEvidence(StrictModel):
    portable: EvidenceFile
    native: Mapping[Identifier, EvidenceFile]
    exports: Mapping[Identifier, EvidenceFile] = Field(default_factory=dict)
    electrical: Mapping[Identifier, EvidenceFile] = Field(default_factory=dict)


class ReleaseManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    release_id: Identifier
    release_class: ReleaseClass
    status: ReleaseStatus
    source_commit: GitCommit
    source_tag: NonEmptyText | None = None
    toolchain_id: Identifier
    projects: tuple[Identifier, ...] = ()
    variants: tuple[ReleaseVariant, ...] = ()
    libraries: tuple[ReleaseLibrary, ...]
    interfaces: tuple[ReleaseInterface, ...]
    checks: Mapping[Identifier, Literal["PASS", "NOT_APPLICABLE"]] = Field(default_factory=dict)
    evidence: ReleaseEvidence | None = None
    artifacts: tuple[ReleaseArtifact, ...]
    deviations: tuple[ReleaseDeviation, ...] = ()
    approval: ReleaseApproval | None = None
