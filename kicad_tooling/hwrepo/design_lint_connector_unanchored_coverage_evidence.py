"""Source-bound evidence for unanchored connector findings with incomplete coverage."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageEntry, ConnectorCoverageReport
from .connector_footprint_peer_pin_types import (
    ConnectorFootprintPeerPinDivergence,
    ConnectorFootprintPeerPinOpenOutlier,
    ConnectorFootprintPeerPinScan,
)
from .design_lint_connector_unanchored_source_evidence import (
    connector_footprint_peer_unanchored_references,
    validate_current_unanchored_peer_contacts,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection

RULE_ID: DesignLintRuleId = "connector.footprint_peer_unanchored_scope_coverage_missing"
INCOMPLETE_COVERAGE_STATUSES = frozenset(
    {"INCOMPLETE", "UNDECLARED", "UNASSESSED", "SCOPE_UNREVIEWED"}
)
REVIEWABLE_ENTRY_STATUSES = frozenset({"COVERED", "UNDECLARED", "INCOMPLETE"})


def connector_coverage_entries_by_reference(
    coverage: ConnectorCoverageReport | None,
) -> Mapping[str, tuple[ConnectorCoverageEntry, ...]]:
    """Index the reviewed connector entries used by unanchored scope findings."""
    mutable: dict[str, list[ConnectorCoverageEntry]] = defaultdict(list)
    if coverage is not None:
        for entry in coverage.entries:
            mutable[entry.reference.casefold()].append(entry)
    return MappingProxyType({reference: tuple(entries) for reference, entries in mutable.items()})


def unanchored_coverage_needs_review(
    references: tuple[str, ...],
    coverage: ConnectorCoverageReport | None,
    entries_by_reference: Mapping[str, Sequence[ConnectorCoverageEntry]],
) -> bool:
    """Apply the rule's incomplete-coverage and per-reference disposition policy."""
    if coverage is None:
        return True
    if coverage.status not in INCOMPLETE_COVERAGE_STATUSES:
        return False
    for reference in references:
        matches = entries_by_reference.get(reference.casefold(), ())
        if len(matches) > 1:
            return False
        if not matches:
            continue
        status = matches[0].status
        if status in {"NOT_APPLICABLE", "STALE"} or status not in REVIEWABLE_ENTRY_STATUSES:
            return False
    return True


@dataclass(frozen=True, slots=True)
class ConnectorUnanchoredCoverageEvidence:
    """One generic alias cohort and the coverage state that leaves it reviewable."""

    scan: ConnectorFootprintPeerPinScan
    coverage: ConnectorCoverageReport | None
    divergences: tuple[ConnectorFootprintPeerPinDivergence, ...]
    partial_opens: tuple[ConnectorFootprintPeerPinOpenOutlier, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "divergences", tuple(self.divergences))
        object.__setattr__(self, "partial_opens", tuple(self.partial_opens))
        _validate_current_unanchored_coverage_evidence(self)

    @classmethod
    def from_scan(
        cls,
        *,
        scan: ConnectorFootprintPeerPinScan,
        coverage: ConnectorCoverageReport | None,
        divergences: tuple[ConnectorFootprintPeerPinDivergence, ...],
        partial_opens: tuple[ConnectorFootprintPeerPinOpenOutlier, ...],
    ) -> ConnectorUnanchoredCoverageEvidence:
        """Capture the exact scan cohort and project coverage supplied to evaluation."""
        return cls(
            scan=scan,
            coverage=coverage,
            divergences=divergences,
            partial_opens=partial_opens,
        )


def _validate_current_unanchored_coverage_evidence(
    source: ConnectorUnanchoredCoverageEvidence,
) -> None:
    coverage = source.coverage
    if coverage is not None and coverage.status not in INCOMPLETE_COVERAGE_STATUSES:
        raise ValueError("Unanchored coverage evidence requires absent or incomplete coverage")
    references, _ = validate_current_unanchored_peer_contacts(
        scan=source.scan,
        divergences=source.divergences,
        partial_opens=source.partial_opens,
    )
    entries = connector_coverage_entries_by_reference(coverage)
    if not unanchored_coverage_needs_review(references, coverage, entries):
        raise ValueError("Unanchored coverage cohort is outside the rule's reviewable scope")

    observed = source.scan.source.observed
    current_pin_evidence = source_matched_connector_pin_evidence(observed, coverage)
    for reference in references:
        for entry in entries.get(reference.casefold(), ()):
            if entry.status == "COVERED" and (
                not entry.mapped_pins
                or any(
                    current_pin_evidence.get(pin.component_pin) != pin for pin in entry.mapped_pins
                )
            ):
                raise ValueError("Unanchored coverage must retain current source-matched pin maps")


def project_connector_unanchored_coverage_evidence(
    source: ConnectorUnanchoredCoverageEvidence,
) -> CandidateEvidenceProjection:
    """Project the established report evidence from the current typed sources."""
    _validate_current_unanchored_coverage_evidence(source)
    items = (*source.divergences, *source.partial_opens)
    first = items[0]
    references = connector_footprint_peer_unanchored_references(first)
    entries_by_reference = connector_coverage_entries_by_reference(source.coverage)
    coverage_status = "NOT_SUPPLIED" if source.coverage is None else source.coverage.status
    review_statuses = tuple(
        f"{reference}={entries_by_reference[reference.casefold()][0].status}"
        if entries_by_reference.get(reference.casefold())
        else f"{reference}=NO_ENTRY"
        for reference in references
    )
    pin_evidence: list[tuple[str, Mapping[str, tuple[str, ...]], bool]] = sorted(
        ((item.pin_number, item.assignments, False) for item in source.divergences),
        key=lambda item: (item[0].casefold(), item[0]),
    )
    pin_evidence.extend((item.pin_number, item.assignments, True) for item in source.partial_opens)
    pin_evidence.sort(key=lambda item: (item[0].casefold(), item[0]))
    has_partial_opens = bool(source.partial_opens)
    evidence: dict[str, tuple[str, ...]] = {
        "value": (first.value,),
        "footprint": (first.footprint,),
        "references": references,
        "symbols": first.symbols,
        "coverage_status": (coverage_status,),
        "connector_review_statuses": review_statuses,
        "unanchored_generic_pin_numbers": tuple(item[0] for item in pin_evidence),
        "pin_assignments": tuple(
            f"pin {pin_number}: "
            + "; ".join(
                f"{pin}={nets[0] if nets else '<unassigned>'}"
                for pin, nets in sorted(
                    assignments.items(), key=lambda pair: (pair[0].casefold(), pair[0])
                )
            )
            for pin_number, assignments, _ in pin_evidence
        ),
    }
    if has_partial_opens:
        evidence["unanchored_partial_open_pin_numbers"] = tuple(
            item.pin_number for item in source.partial_opens
        )
    return CandidateEvidenceProjection(rule_id=RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class ConnectorUnanchoredCoverageCandidate(Candidate):
    """Coverage finding that retains its exact scan and optional review report."""

    source_evidence: ConnectorUnanchoredCoverageEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorUnanchoredCoverageEvidence,
    ) -> ConnectorUnanchoredCoverageCandidate:
        projection = project_connector_unanchored_coverage_evidence(source_evidence)
        items = (*source_evidence.divergences, *source_evidence.partial_opens)
        first = items[0]
        has_partial_opens = bool(source_evidence.partial_opens)
        has_divergences = bool(source_evidence.divergences)
        subject_suffix = (
            "unanchored connector alias splits lack complete coverage"
            if has_divergences and not has_partial_opens
            else "unanchored connector alias partial opens lack complete coverage"
            if has_partial_opens and not has_divergences
            else "unanchored connector alias splits and partial opens lack complete coverage"
        )
        message = (
            "Fitted connector aliases have exact generic-pin assignments to different nets without "
            "a common-net anchor, while the project-wide connector inventory or coverage review is "
            "incomplete. Review the pinouts and whether these references should be compared as peers "
            "or remain separate. Similarity does not establish matching pin roles or require any "
            "contacts to be joined."
        )
        if has_partial_opens:
            message = (
                "Fitted connector aliases have unanchored generic-pin assignments with one or more "
                "open peer contacts, while the project-wide connector inventory or coverage review "
                "is incomplete. Review the pinouts and whether these references should be compared "
                "as peers or remain separate. Similarity does not establish matching pin roles or a "
                "required connection."
            )
        return cls(
            rule_id=projection.rule_id,
            subject=f"{first.value} [{first.footprint}]: {subject_suffix}",
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_connector_unanchored_coverage_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError(
                "Unanchored coverage fields must match their current source projection"
            )
