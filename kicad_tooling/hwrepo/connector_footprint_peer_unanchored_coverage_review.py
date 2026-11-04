"""Review unanchored connector-alias assignments without complete coverage."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass

from .connector_coverage_models import ConnectorCoverageEntry, ConnectorCoverageReport
from .connector_footprint_peer_pin_types import (
    ConnectorFootprintPeerPinDivergence,
    ConnectorFootprintPeerPinOpenOutlier,
    ConnectorFootprintPeerPinScan,
)
from .connector_identity import pin_function_is_generic
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate

RULE_ID: DesignLintRuleId = "connector.footprint_peer_unanchored_scope_coverage_missing"
INCOMPLETE_COVERAGE_STATUSES = frozenset(
    {"INCOMPLETE", "UNDECLARED", "UNASSESSED", "SCOPE_UNREVIEWED"}
)
REVIEWABLE_ENTRY_STATUSES = frozenset({"COVERED", "UNDECLARED", "INCOMPLETE"})


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

    entries_by_reference: dict[str, list[ConnectorCoverageEntry]] = defaultdict(list)
    if coverage is not None:
        for entry in coverage.entries:
            entries_by_reference[entry.reference.casefold()].append(entry)

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
        references = _references_for(evidence_items[0])
        if not _coverage_needs_review(references, coverage, entries_by_reference):
            continue
        candidates.append(_candidate(cohort, coverage, entries_by_reference))
    return tuple(candidates)


def _cohort_for(
    item: ConnectorFootprintPeerPinDivergence | ConnectorFootprintPeerPinOpenOutlier,
    cohorts: MutableMapping[
        tuple[str, str, tuple[str, ...], tuple[str, ...]], _UnanchoredAliasCohort
    ],
) -> _UnanchoredAliasCohort:
    references = _references_for(item)
    key = (
        item.value.casefold(),
        item.footprint.casefold(),
        tuple(reference.casefold() for reference in references),
        tuple(symbol.casefold() for symbol in item.symbols),
    )
    return cohorts.setdefault(key, _UnanchoredAliasCohort(divergences=[], partial_opens=[]))


def _references_for(
    item: ConnectorFootprintPeerPinDivergence | ConnectorFootprintPeerPinOpenOutlier,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {pin.rsplit(".", 1)[0] for pin in item.assignments},
            key=lambda reference: (reference.casefold(), reference),
        )
    )


def _coverage_needs_review(
    references: tuple[str, ...],
    coverage: ConnectorCoverageReport | None,
    entries_by_reference: Mapping[str, Sequence[ConnectorCoverageEntry]],
) -> bool:
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


def _candidate(
    cohort: _UnanchoredAliasCohort,
    coverage: ConnectorCoverageReport | None,
    entries_by_reference: Mapping[str, Sequence[ConnectorCoverageEntry]],
) -> Candidate:
    evidence_items = (*cohort.divergences, *cohort.partial_opens)
    first = evidence_items[0]
    references = _references_for(first)
    coverage_status = "NOT_SUPPLIED" if coverage is None else coverage.status
    review_statuses = tuple(
        f"{reference}={entries_by_reference[reference.casefold()][0].status}"
        if entries_by_reference.get(reference.casefold())
        else f"{reference}=NO_ENTRY"
        for reference in references
    )
    pin_evidence = sorted(
        ((item.pin_number, item.assignments, False) for item in cohort.divergences),
        key=lambda item: (item[0].casefold(), item[0]),
    )
    pin_evidence.extend((item.pin_number, item.assignments, True) for item in cohort.partial_opens)
    pin_evidence.sort(key=lambda item: (item[0].casefold(), item[0]))
    pin_assignments = tuple(
        f"pin {pin_number}: "
        + "; ".join(
            f"{pin}={nets[0] if nets else '<unassigned>'}"
            for pin, nets in sorted(
                assignments.items(), key=lambda pair: (pair[0].casefold(), pair[0])
            )
        )
        for pin_number, assignments, _ in pin_evidence
    )
    has_partial_opens = bool(cohort.partial_opens)
    has_divergences = bool(cohort.divergences)
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
            "open peer contacts, while the project-wide connector inventory or coverage review is "
            "incomplete. Review the pinouts and whether these references should be compared as "
            "peers or remain separate. Similarity does not establish matching pin roles or a "
            "required connection."
        )
    evidence: dict[str, tuple[str, ...]] = {
        "value": (first.value,),
        "footprint": (first.footprint,),
        "references": references,
        "symbols": first.symbols,
        "coverage_status": (coverage_status,),
        "connector_review_statuses": review_statuses,
        "unanchored_generic_pin_numbers": tuple(item[0] for item in pin_evidence),
        "pin_assignments": pin_assignments,
    }
    if has_partial_opens:
        evidence["unanchored_partial_open_pin_numbers"] = tuple(
            item.pin_number for item in cohort.partial_opens
        )
    return Candidate(
        rule_id=RULE_ID,
        subject=f"{first.value} [{first.footprint}]: {subject_suffix}",
        message=message,
        evidence=evidence,
    )
