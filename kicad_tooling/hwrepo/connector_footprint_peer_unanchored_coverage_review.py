"""Review unanchored connector-alias splits without complete coverage review."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage_models import ConnectorCoverageEntry, ConnectorCoverageReport
from .connector_footprint_peer_pin_types import (
    ConnectorFootprintPeerPinDivergence,
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


def uncovered_unanchored_connector_alias_scope(
    scan: ConnectorFootprintPeerPinScan,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Prompt on exact unanchored alias splits when project coverage is absent or incomplete."""
    if coverage is not None and coverage.status not in INCOMPLETE_COVERAGE_STATUSES:
        return ()

    entries_by_reference: dict[str, list[ConnectorCoverageEntry]] = defaultdict(list)
    if coverage is not None:
        for entry in coverage.entries:
            entries_by_reference[entry.reference.casefold()].append(entry)

    cohorts: dict[
        tuple[str, str, tuple[str, ...], tuple[str, ...]],
        list[ConnectorFootprintPeerPinDivergence],
    ] = defaultdict(list)
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
        references = tuple(
            sorted(
                {pin.rsplit(".", 1)[0] for pin in divergence.assignments},
                key=lambda reference: (reference.casefold(), reference),
            )
        )
        if not _coverage_needs_review(references, coverage, entries_by_reference):
            continue
        cohorts[
            (
                divergence.value.casefold(),
                divergence.footprint.casefold(),
                tuple(reference.casefold() for reference in references),
                tuple(symbol.casefold() for symbol in divergence.symbols),
            )
        ].append(divergence)

    return tuple(
        _candidate(divergences, coverage, entries_by_reference)
        for _, divergences in sorted(cohorts.items())
    )


def _coverage_needs_review(
    references: tuple[str, ...],
    coverage: ConnectorCoverageReport | None,
    entries_by_reference: dict[str, list[ConnectorCoverageEntry]],
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
    divergences: list[ConnectorFootprintPeerPinDivergence],
    coverage: ConnectorCoverageReport | None,
    entries_by_reference: dict[str, list[ConnectorCoverageEntry]],
) -> Candidate:
    first = divergences[0]
    references = tuple(
        sorted(
            {pin.rsplit(".", 1)[0] for pin in first.assignments},
            key=lambda reference: (reference.casefold(), reference),
        )
    )
    coverage_status = "NOT_SUPPLIED" if coverage is None else coverage.status
    review_statuses = tuple(
        f"{reference}={entries_by_reference[reference.casefold()][0].status}"
        if entries_by_reference.get(reference.casefold())
        else f"{reference}=NO_ENTRY"
        for reference in references
    )
    ordered_divergences = sorted(
        divergences,
        key=lambda item: (item.pin_number.casefold(), item.pin_number),
    )
    pin_assignments = tuple(
        f"pin {item.pin_number}: "
        + "; ".join(
            f"{pin}={nets[0]}"
            for pin, nets in sorted(
                item.assignments.items(), key=lambda pair: (pair[0].casefold(), pair[0])
            )
        )
        for item in ordered_divergences
    )
    return Candidate(
        rule_id=RULE_ID,
        subject=(
            f"{first.value} [{first.footprint}]: unanchored connector alias splits lack complete coverage"
        ),
        message=(
            "Fitted connector aliases have exact generic-pin assignments to different nets without "
            "a common-net anchor, while the project-wide connector inventory or coverage review is "
            "incomplete. Review the pinouts and whether these references should be compared as peers "
            "or remain separate. Similarity does not establish matching pin roles or require any "
            "contacts to be joined."
        ),
        evidence={
            "value": (first.value,),
            "footprint": (first.footprint,),
            "references": references,
            "symbols": first.symbols,
            "coverage_status": (coverage_status,),
            "connector_review_statuses": review_statuses,
            "unanchored_generic_pin_numbers": tuple(
                item.pin_number for item in ordered_divergences
            ),
            "pin_assignments": pin_assignments,
        },
    )
