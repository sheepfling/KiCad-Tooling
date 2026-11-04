"""Typed source projections for connector and net return-domain findings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeAlias

from .connector_return_pins import ConnectorReturnCoverage
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .return_net_models import ReturnNetGroup


@dataclass(frozen=True, slots=True)
class ConnectorNoReturnEvidence:
    """Connector scan coverage and any return-like labels needing role review."""

    coverage: ConnectorReturnCoverage
    return_named_net_candidates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "return_named_net_candidates",
            tuple(self.return_named_net_candidates),
        )


@dataclass(frozen=True, slots=True)
class NumberedReturnEvidence:
    """A numbered return group retained for the common-domain review prompt."""

    group: ReturnNetGroup


@dataclass(frozen=True, slots=True)
class UnroledReturnLabelsEvidence:
    """A group of return-like labels whose pins have no native return role."""

    group: ReturnNetGroup


ReturnCandidateSource: TypeAlias = (
    ConnectorNoReturnEvidence | NumberedReturnEvidence | UnroledReturnLabelsEvidence
)

_CONNECTOR_NO_RETURN: DesignLintRuleId = "connector.no_connected_return"
_NUMBERED_RETURNS: DesignLintRuleId = "net.numbered_returns"
_UNROLED_RETURN_LABELS: DesignLintRuleId = "net.return_labels_without_pin_roles"


def _string_tuples(values: Mapping[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """Project typed pin/net mappings into the stable report value type."""
    return {str(key): tuple(str(value) for value in items) for key, items in values.items()}


def project_return_candidate_evidence(
    source: ReturnCandidateSource,
) -> CandidateEvidenceProjection:
    """Map a return-domain source variant to its established report fields."""
    if isinstance(source, ConnectorNoReturnEvidence):
        evidence = _string_tuples(source.coverage.pins)
        if source.return_named_net_candidates:
            evidence["return_named_net_candidates"] = source.return_named_net_candidates
        return CandidateEvidenceProjection(rule_id=_CONNECTOR_NO_RETURN, evidence=evidence)
    if isinstance(source, NumberedReturnEvidence):
        return CandidateEvidenceProjection(
            rule_id=_NUMBERED_RETURNS,
            evidence=_string_tuples(source.group.nets),
        )
    return CandidateEvidenceProjection(
        rule_id=_UNROLED_RETURN_LABELS,
        evidence=_string_tuples(source.group.nets),
    )


@dataclass(frozen=True, slots=True)
class ReturnDomainCandidate(Candidate):
    """Return-domain finding retaining its connector or net-group scan source."""

    source_evidence: ReturnCandidateSource

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ReturnCandidateSource,
        *,
        subject: str,
        message: str,
    ) -> ReturnDomainCandidate:
        projection = project_return_candidate_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_return_candidate_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Return candidate fields must match their typed source projection")
