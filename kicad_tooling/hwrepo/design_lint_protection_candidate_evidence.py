"""Typed source evidence and projections for external-protection findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .external_protection_models import (
    ExternalProtectionCoverageEntry,
    ExternalProtectionCoverageReport,
)

UNREVIEWED_RULE_ID: DesignLintRuleId = "protection.unreviewed_interface_pin"
MISMATCH_RULE_ID: DesignLintRuleId = "protection.mapped_device_mismatch"


@dataclass(frozen=True, slots=True)
class UnreviewedProtectionFindingEvidence:
    """An undeclared interface pin retained with its current coverage report."""

    report: ExternalProtectionCoverageReport
    entry: ExternalProtectionCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status not in {"INCOMPLETE", "UNDECLARED"}:
            raise ValueError("Unreviewed protection evidence requires unresolved coverage")
        if self.entry not in self.report.entries or self.entry.status != "UNDECLARED":
            raise ValueError("Unreviewed protection evidence requires a matching undeclared entry")


def project_unreviewed_protection_evidence(
    source: UnreviewedProtectionFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the connector and observed net identity for an applicability prompt."""
    entry = source.entry
    return CandidateEvidenceProjection(
        rule_id=UNREVIEWED_RULE_ID,
        evidence={
            "connector": (entry.connector_reference,),
            "signal": (entry.interface_signal or "unknown",),
            "net": entry.observed_nets,
        },
    )


@dataclass(frozen=True, slots=True)
class UnreviewedProtectionCandidate(Candidate):
    """Applicability prompt retaining its source coverage entry and report."""

    source_evidence: UnreviewedProtectionFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UnreviewedProtectionFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> UnreviewedProtectionCandidate:
        projection = project_unreviewed_protection_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_unreviewed_protection_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Unreviewed protection evidence must match its source projection")


@dataclass(frozen=True, slots=True)
class ProtectionMismatchFindingEvidence:
    """An incomplete or stale mapped channel retained with its coverage report."""

    report: ExternalProtectionCoverageReport
    entry: ExternalProtectionCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status != "INCOMPLETE":
            raise ValueError("Protection mismatch evidence requires incomplete coverage")
        if self.entry not in self.report.entries or self.entry.status not in {
            "INCOMPLETE",
            "STALE",
        }:
            raise ValueError("Protection mismatch evidence requires a matching incomplete entry")


def project_protection_mismatch_evidence(
    source: ProtectionMismatchFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the expected and observed protection mapping for review."""
    entry = source.entry
    return CandidateEvidenceProjection(
        rule_id=MISMATCH_RULE_ID,
        evidence={
            "connector": (entry.connector_reference,),
            "signal": (entry.interface_signal or "unknown",),
            "expected_net": (entry.signal_net or "<not declared>",),
            "observed_nets": entry.observed_nets,
            "protection_devices": entry.device_references,
            "issues": entry.issues,
        },
    )


@dataclass(frozen=True, slots=True)
class ProtectionMismatchCandidate(Candidate):
    """Mapped-device finding retaining its source entry and coverage report."""

    source_evidence: ProtectionMismatchFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ProtectionMismatchFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> ProtectionMismatchCandidate:
        projection = project_protection_mismatch_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_protection_mismatch_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Protection mismatch evidence must match its source projection")
