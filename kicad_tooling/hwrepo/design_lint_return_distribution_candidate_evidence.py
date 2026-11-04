"""Typed evidence projection for authored connector return-distribution findings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .connector_return_distribution_models import (
    ConnectorReturnDistributionCoverageReport,
    ConnectorReturnDistributionEntry,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .model_primitives import NonEmptyText, Reference

_RULE_ID: DesignLintRuleId = "connector.return_distribution"


@dataclass(frozen=True, slots=True)
class ConnectorReturnDistributionFindingEvidence:
    """One non-complete entry retained with its source-bound coverage report."""

    coverage: ConnectorReturnDistributionCoverageReport
    entry: ConnectorReturnDistributionEntry

    def __post_init__(self) -> None:
        if self.coverage.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("Return-distribution finding evidence requires scanned coverage")
        if self.entry.status not in {"OUT_OF_RANGE", "INCOMPLETE"}:
            raise ValueError("Return-distribution finding evidence requires an open entry")
        if not any(candidate is self.entry for candidate in self.coverage.entries):
            raise ValueError("Return-distribution entry must belong to its source coverage report")


def _pin_assignments(pin_map: Mapping[NonEmptyText, Reference]) -> tuple[str, ...]:
    """Format a typed interface-number to connector-pin assignment map."""
    return tuple(f"interface {number} -> {pin}" for number, pin in sorted(pin_map.items()))


def project_return_distribution_evidence(
    source: ConnectorReturnDistributionFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the exact entry into the stable connector return report fields."""
    entry = source.entry
    ratio = (
        "undefined (no return contacts)"
        if entry.signal_to_return_ratio is None
        else f"{entry.signal_to_return_ratio:g} signals per return"
    )
    evidence = {
        "profile": (entry.id,),
        "connector": (entry.connector_reference or "<no bound connector>",),
        "interface": (entry.interface_id,),
        "signal_contact_count": (str(entry.signal_pin_count),),
        "signal_pins": _pin_assignments(entry.signal_pin_map),
        "return_contact_count": (str(entry.return_pin_count),),
        "return_pins": _pin_assignments(entry.return_pin_map),
        "supply_pins_excluded": _pin_assignments(entry.supply_pin_map),
        "shield_pins_excluded": _pin_assignments(entry.shield_pin_map),
        "other_pins_excluded": _pin_assignments(entry.other_pin_map),
        "unclassified_pins": _pin_assignments(entry.unclassified_pin_map),
        "required_return_contact_count": (str(entry.required_return_pin_count),),
        "signal_to_return_ratio": (ratio,),
        "minimum_signal_pin_count": (str(entry.minimum_signal_pin_count),),
        "maximum_signal_to_return_ratio": (f"{entry.maximum_signal_to_return_ratio:g}",),
        "basis": (entry.basis,),
        "issues": entry.issues,
    }
    return CandidateEvidenceProjection(rule_id=_RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class ConnectorReturnDistributionCandidate(Candidate):
    """Return-distribution finding retaining entry and report source identity."""

    source_evidence: ConnectorReturnDistributionFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorReturnDistributionFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> ConnectorReturnDistributionCandidate:
        projection = project_return_distribution_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_return_distribution_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Return-distribution fields must match their typed source projection")
