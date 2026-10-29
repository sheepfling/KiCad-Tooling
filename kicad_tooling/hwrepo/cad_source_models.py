"""Typed contracts for sourced CAD bundles and their review/import lifecycle."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from .command_evidence_models import CommandEvidence
from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel


class CadProviderIdentity(StrictModel):
    supplier_id: Annotated[str, StringConstraints(pattern=r"^C[1-9][0-9]*$")]
    component_supplier_id: Annotated[str, StringConstraints(pattern=r"^C[1-9][0-9]*$")]
    manufacturer: NonEmptyText
    mpn: NonEmptyText
    package: NonEmptyText
    symbol_name: NonEmptyText
    model_uuid: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]
    model_title: str = ""


class CadSourceFile(StrictModel):
    path: RepositoryPath
    sha256: Digest
    source_url: str | None = None


class CadSourceBundle(StrictModel):
    schema_version: Literal["1"] = "1"
    provider: Literal["easyeda"] = "easyeda"
    supplier_id: Annotated[str, StringConstraints(pattern=r"^C[1-9][0-9]*$")]
    manufacturer: NonEmptyText
    mpn: NonEmptyText
    package: NonEmptyText
    symbol_file: RepositoryPath
    symbol_name: NonEmptyText
    footprint_file: RepositoryPath
    footprint_name: NonEmptyText
    model_file: RepositoryPath
    files: tuple[CadSourceFile, ...]
    source_url: NonEmptyText
    source_sha256: Digest
    retrieved_at: NonEmptyText
    converter_version: Literal["1.0.1"] = "1.0.1"
    converter_sha256: Digest | None = None
    issues: tuple[NonEmptyText, ...] = ()


class CadSourceReport(StrictModel):
    status: Literal["READY", "BLOCKED"]
    supplier_id: str
    bundle_directory: str | None = None
    bundle: CadSourceBundle | None = None
    cache_hit: bool = False
    issues: tuple[NonEmptyText, ...] = ()
    receipt_directory: str


class CadStepReport(StrictModel):
    schema_version: Literal["1"] = "1"
    status: Literal["REVIEW", "BLOCKED"]
    project_id: Identifier
    supplier_id: str
    source_bundle_sha256: Digest | None = None
    source_step_sha256: Digest | None = None
    kicad_version: str | None = None
    image: str | None = None
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    commands: Mapping[str, CommandEvidence] = Field(default_factory=dict)
    issues: tuple[NonEmptyText, ...] = ()
    receipt_directory: str
    alignment_verified: Literal[False] = False
    physical_fit_verified: Literal[False] = False


class CadBundleCheck(StrictModel):
    status: Literal["READY", "BLOCKED"]
    symbol_pins: tuple[str, ...] = ()
    footprint_pads: tuple[str, ...] = ()
    model_references: tuple[str, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    physical_fit_verified: Literal[False] = False


class CadImportPlan(StrictModel):
    schema_version: Literal["1"] = "1"
    project_id: Identifier
    bundle_dir: str
    bundle_sha256: Digest
    preconditions: Mapping[RepositoryPath, Digest | None]
    after_hashes: Mapping[RepositoryPath, Digest]


class CadImportReport(StrictModel):
    status: Literal["PLAN", "APPLIED", "BLOCKED"]
    project_id: Identifier
    symbol_id: str | None = None
    footprint_id: str | None = None
    files: tuple[RepositoryPath, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    check: CadBundleCheck | None = None
    plan_path: str | None = None
    receipt_directory: str
    diff: str = ""
    build_authorized: Literal[False] = False


class CadSourcingReview(StrictModel):
    source: CadSourceReport
    import_plan: CadImportReport | None = None
    review_id: str
