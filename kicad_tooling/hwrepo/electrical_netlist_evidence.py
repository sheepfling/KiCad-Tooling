"""Admit source-bound contract-coach observations into electrical evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal, TypeAlias

from pydantic import Field, model_validator

from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel
from .models import ContractCoachReport, NetlistContract


class NetlistEvidenceNotRequested(StrictModel):
    """No configured electrical requirement requested a native netlist."""

    state: Literal["NOT_REQUESTED"] = "NOT_REQUESTED"
    project_id: Identifier


class NetlistEvidenceUnavailable(StrictModel):
    """A capture was requested but did not yield admissible netlist evidence."""

    state: Literal["UNAVAILABLE"] = "UNAVAILABLE"
    project_id: Identifier
    expected_source_sha256: Mapping[RepositoryPath, Digest]
    report: ContractCoachReport
    reason: NonEmptyText

    @model_validator(mode="after")
    def report_is_not_admissible(self) -> NetlistEvidenceUnavailable:
        if self.report.project_id != self.project_id:
            raise ValueError("Netlist evidence belongs to another project")
        if (
            self.report.status == "READY_FOR_REVIEW"
            and self.report.observed is not None
            and self.report.netlist_sha256 is not None
            and dict(self.report.source_hashes) == dict(self.expected_source_sha256)
        ):
            raise ValueError("Current source-bound netlist evidence cannot be marked unavailable")
        return self


class NetlistEvidenceObserved(StrictModel):
    """A native netlist report admitted against the current project source set."""

    state: Literal["OBSERVED"] = "OBSERVED"
    project_id: Identifier
    expected_source_sha256: Mapping[RepositoryPath, Digest]
    report: ContractCoachReport

    @model_validator(mode="after")
    def report_matches_current_sources(self) -> NetlistEvidenceObserved:
        if self.report.project_id != self.project_id:
            raise ValueError("Netlist evidence belongs to another project")
        if self.report.status != "READY_FOR_REVIEW":
            raise ValueError("Only a ready source-bound netlist can enter electrical evaluation")
        if self.report.observed is None or self.report.netlist_sha256 is None:
            raise ValueError("Electrical netlist evidence needs an observation and its digest")
        if dict(self.report.source_hashes) != dict(self.expected_source_sha256):
            raise ValueError("Netlist evidence does not match the current declared project sources")
        return self

    @property
    def observed(self) -> NetlistContract:
        observation = self.report.observed
        if observation is None:  # The model validator enforces this invariant.
            raise AssertionError("Admitted netlist evidence lost its observation")
        return observation


ElectricalNetlistEvidence: TypeAlias = Annotated[
    NetlistEvidenceNotRequested | NetlistEvidenceUnavailable | NetlistEvidenceObserved,
    Field(discriminator="state"),
]


def admit_netlist_evidence(
    report: ContractCoachReport,
    project_id: str,
    expected_source_sha256: Mapping[RepositoryPath, Digest],
) -> NetlistEvidenceUnavailable | NetlistEvidenceObserved:
    """Retain capture provenance and admit only the current project's observation."""
    if report.project_id != project_id:
        raise ValueError("Netlist evidence belongs to another project")
    if report.status != "READY_FOR_REVIEW":
        return NetlistEvidenceUnavailable(
            project_id=project_id,
            expected_source_sha256=expected_source_sha256,
            report=report,
            reason="The native netlist capture is blocked.",
        )
    if report.observed is None or report.netlist_sha256 is None:
        return NetlistEvidenceUnavailable(
            project_id=project_id,
            expected_source_sha256=expected_source_sha256,
            report=report,
            reason="The native netlist report has no source-bound observation and digest.",
        )
    if dict(report.source_hashes) != dict(expected_source_sha256):
        return NetlistEvidenceUnavailable(
            project_id=project_id,
            expected_source_sha256=expected_source_sha256,
            report=report,
            reason="The native netlist does not match the current declared project sources.",
        )
    return NetlistEvidenceObserved(
        project_id=project_id,
        expected_source_sha256=expected_source_sha256,
        report=report,
    )
