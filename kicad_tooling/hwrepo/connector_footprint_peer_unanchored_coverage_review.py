"""Review unanchored connector-alias assignments without complete coverage."""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass

from .connector_coverage_models import ConnectorCoverageReport
from .connector_footprint_peer_pin_types import (
    SIGNAL_ELECTRICAL_TYPES,
    ConnectorFootprintPeerPinDivergence,
    ConnectorFootprintPeerPinOpenOutlier,
    ConnectorFootprintPeerPinScan,
)
from .connector_identity import pin_function_is_generic
from .design_lint_connector_unanchored_coverage_evidence import (
    INCOMPLETE_COVERAGE_STATUSES,
    ConnectorUnanchoredCoverageCandidate,
    ConnectorUnanchoredCoverageEvidence,
    connector_coverage_entries_by_reference,
    unanchored_coverage_needs_review,
)
from .design_lint_connector_unanchored_source_evidence import (
    connector_footprint_peer_unanchored_cohort_key,
    connector_footprint_peer_unanchored_references,
)
from .design_lint_types import Candidate


@dataclass(slots=True)
class _UnanchoredAliasCohort:
    """Generic pin evidence grouped by the bounded footprint-alias cohort."""

    divergences: list[ConnectorFootprintPeerPinDivergence]
    partial_opens: list[ConnectorFootprintPeerPinOpenOutlier]


def uncovered_unanchored_connector_alias_scope(
    scan: ConnectorFootprintPeerPinScan,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Prompt on unanchored alias splits or partial opens without complete coverage."""
    if coverage is not None and coverage.status not in INCOMPLETE_COVERAGE_STATUSES:
        return ()

    entries_by_reference = connector_coverage_entries_by_reference(coverage)

    cohorts: dict[
        tuple[str, str, tuple[str, ...], tuple[str, ...]],
        _UnanchoredAliasCohort,
    ] = {}
    for divergence in scan.unanchored_divergences:
        if (
            divergence.peer_assignment_group is not None
            or divergence.common_anchor_pin_numbers
            or not pin_function_is_generic(divergence.pin_function)
            or len(divergence.assignments) < 2
            or any(len(nets) != 1 for nets in divergence.assignments.values())
            or len({nets[0] for nets in divergence.assignments.values()}) < 2
        ):
            continue
        _cohort_for(divergence, cohorts).divergences.append(divergence)

    for partial_open in scan.unanchored_open_outliers:
        assignments = partial_open.assignments
        assigned_nets = {nets[0] for nets in assignments.values() if len(nets) == 1}
        if (
            partial_open.peer_assignment_group is not None
            or partial_open.common_anchor_pin_numbers
            or not pin_function_is_generic(partial_open.pin_function)
            or partial_open.pin_electrical_type.strip().casefold()
            not in {"passive", *SIGNAL_ELECTRICAL_TYPES}
            or len(assignments) < 2
            or any(len(nets) > 1 for nets in assignments.values())
            or not any(not nets for nets in assignments.values())
            or not assigned_nets
        ):
            continue
        _cohort_for(partial_open, cohorts).partial_opens.append(partial_open)

    candidates: list[Candidate] = []
    for _, cohort in sorted(cohorts.items()):
        evidence_items = (*cohort.divergences, *cohort.partial_opens)
        references = connector_footprint_peer_unanchored_references(evidence_items[0])
        if not unanchored_coverage_needs_review(references, coverage, entries_by_reference):
            continue
        candidates.append(_candidate(scan, cohort, coverage))
    return tuple(candidates)


def _cohort_for(
    item: ConnectorFootprintPeerPinDivergence | ConnectorFootprintPeerPinOpenOutlier,
    cohorts: MutableMapping[
        tuple[str, str, tuple[str, ...], tuple[str, ...]], _UnanchoredAliasCohort
    ],
) -> _UnanchoredAliasCohort:
    key = connector_footprint_peer_unanchored_cohort_key(item)
    return cohorts.setdefault(key, _UnanchoredAliasCohort(divergences=[], partial_opens=[]))


def _candidate(
    scan: ConnectorFootprintPeerPinScan,
    cohort: _UnanchoredAliasCohort,
    coverage: ConnectorCoverageReport | None,
) -> Candidate:
    source_evidence = ConnectorUnanchoredCoverageEvidence.from_scan(
        scan=scan,
        coverage=coverage,
        divergences=tuple(cohort.divergences),
        partial_opens=tuple(cohort.partial_opens),
    )
    return ConnectorUnanchoredCoverageCandidate.from_source_evidence(source_evidence)
