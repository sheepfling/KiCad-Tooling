"""Bind project verification summaries to source and retained stage files."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .contracts import read_model, repo_path, write_model
from .evidence import digest
from .model_primitives import Digest, RepositoryPath, StrictModel
from .repository import checkout_input_hashes


class VerificationOutputManifest(StrictModel):
    """A run-start checkout inventory and hash-bound top-level output inventory."""

    schema_version: Literal["1"] = "1"
    report_sha256: Digest
    source_stable: bool
    source_hashes: Mapping[RepositoryPath, Digest] = Field(min_length=1)
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(min_length=1)

    @model_validator(mode="after")
    def required_journal_files(self) -> VerificationOutputManifest:
        if not {"verification.txt", "run.json", "events.log"} <= self.artifacts_sha256.keys():
            raise ValueError("Verification manifest must bind its journal outputs")
        return self


def save_verification_output_manifest(
    root: Path, directory: Path, start_hashes: Mapping[str, str]
) -> VerificationOutputManifest:
    """Save evidence after journal closure, including failed verification runs."""
    report = repo_path(directory, "verification.json")
    outputs: dict[str, str] = {}
    for path in sorted(directory.iterdir()):
        if path.is_symlink():
            raise ValueError(f"Verification output is a symlink: {path.name}")
        if path.is_file() and path.name != report.name:
            outputs[path.name] = digest(path)
    if not {"verification.txt", "run.json", "events.log"} <= outputs.keys():
        raise ValueError("Verification receipt is missing its journal outputs")
    end_hashes = checkout_input_hashes(root)
    manifest = VerificationOutputManifest(
        report_sha256=digest(report),
        source_stable=dict(start_hashes) == end_hashes,
        source_hashes=dict(start_hashes),
        artifacts_sha256=outputs,
    )
    temporary = directory / "verification-artifacts.json.tmp"
    write_model(temporary, manifest)
    temporary.replace(directory / "verification-artifacts.json")
    return manifest


def read_verification_output_manifest(
    directory: Path, report_sha256: str
) -> VerificationOutputManifest | None:
    """Legacy summaries may have no manifest; a present one must bind the report."""
    path = directory / "verification-artifacts.json"
    if path.is_symlink():
        raise ValueError("Verification artifact manifest must be a regular local file")
    if not path.exists():
        return None
    manifest = read_model(repo_path(directory, path.name), VerificationOutputManifest)
    if manifest.report_sha256 != report_sha256:
        raise ValueError("Verification artifact manifest does not bind the selected report")
    return manifest
