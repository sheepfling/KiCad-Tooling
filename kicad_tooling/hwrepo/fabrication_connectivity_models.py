"""Project policy and source-bound evidence for fabrication connectivity review."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Digest, NonEmptyText, RepositoryPath, StrictModel


class FabricationConnectivityIgnore(StrictModel):
    """One exact analyzer finding a project has reviewed as intentional."""

    fingerprint: Digest
    reason: NonEmptyText


class FabricationConnectivitySettings(StrictModel):
    """Opt-in policy for comparing supported Gerber output with IPC-D-356."""

    mode: Literal["review", "block"] = "review"
    pixel_density: Literal[25, 50, 100] = 50
    ignores: tuple[FabricationConnectivityIgnore, ...] = ()

    @model_validator(mode="after")
    def unique_ignores(self) -> FabricationConnectivitySettings:
        fingerprints = tuple(item.fingerprint for item in self.ignores)
        if len(set(fingerprints)) != len(fingerprints):
            raise ValueError("fabrication connectivity ignore fingerprints must be unique")
        return self


class FabricationConnectivityDrillEvidence(StrictModel):
    """Physical geometry for an Excellon hit with no source pad/via owner."""

    plating: Literal["plated", "nonplated"]
    start_mm: tuple[float, float]
    end_mm: tuple[float, float] | None = None
    diameter_mm: float
    multiplicity: Annotated[int, Field(ge=1)]


class FabricationConnectivityFinding(StrictModel):
    """A source- and artifact-local connectivity observation."""

    code: Literal["OPEN", "SHORT", "NO_COPPER", "NO_DRILL", "UNBOUND_DRILL_HIT"]
    fingerprint: Digest
    net: NonEmptyText | None = None
    contacts: tuple[NonEmptyText, ...] = ()
    location_mm: tuple[float, float] | None = None
    drill_evidence: FabricationConnectivityDrillEvidence | None = None

    @model_validator(mode="after")
    def drill_evidence_matches_code(self) -> FabricationConnectivityFinding:
        if (self.code == "UNBOUND_DRILL_HIT") != (self.drill_evidence is not None):
            raise ValueError("unbound drill findings require exactly one drill evidence record")
        return self


class FabricationConnectivitySummary(StrictModel):
    """Reproducible result whose input files are bound by SHA-256."""

    schema_version: Literal["1"] = "1"
    analyzer_version: Literal["24"] = "24"
    status: Literal["PASS", "REVIEW", "FAIL", "UNSUPPORTED"]
    board_sha256: Digest
    artifact_sha256: Mapping[RepositoryPath, Digest]
    pixel_density: Literal[25, 50, 100]
    findings: tuple[FabricationConnectivityFinding, ...] = ()
    ignored_findings: tuple[FabricationConnectivityFinding, ...] = ()
    stale_ignore_fingerprints: tuple[Digest, ...] = ()
    unsupported_reasons: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def normalize_evidence(self) -> FabricationConnectivitySummary:
        artifacts = dict(sorted(self.artifact_sha256.items()))
        object.__setattr__(self, "artifact_sha256", artifacts)
        object.__setattr__(
            self, "findings", tuple(sorted(self.findings, key=lambda x: x.fingerprint))
        )
        object.__setattr__(
            self,
            "ignored_findings",
            tuple(sorted(self.ignored_findings, key=lambda x: x.fingerprint)),
        )
        object.__setattr__(
            self, "stale_ignore_fingerprints", tuple(sorted(self.stale_ignore_fingerprints))
        )
        return self
