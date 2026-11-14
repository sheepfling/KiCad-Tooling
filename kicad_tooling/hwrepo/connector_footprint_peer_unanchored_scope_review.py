"""Review unanchored connector alias splits when comparison scope is absent."""

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
from .design_lint_connector_unanchored_scope_evidence import (
    ConnectorUnanchoredPeerScopeCandidate,
    ConnectorUnanchoredPeerScopeEvidence,
    references_have_current_unscoped_maps,
)
from .design_lint_connector_unanchored_source_evidence import (
    connector_footprint_peer_unanchored_cohort_key,
    connector_footprint_peer_unanchored_references,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract


@dataclass(slots=True)
class _UnanchoredAliasCohort:
    """Eligible divergent and partial-open contacts for one alias cohort."""

    divergences: list[ConnectorFootprintPeerPinDivergence]
    partial_opens: list[ConnectorFootprintPeerPinOpenOutlier]


def unreviewed_unanchored_connector_alias_scope(
    scan: ConnectorFootprintPeerPinScan,
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Prompt once per alias cohort with current pin maps but no peer decision."""
    if (
        coverage is None
        or coverage.status != "COMPLETE"
        or coverage.inventory_review_basis is None
        or coverage.interface_catalog_sha256 is None
    ):
        return ()

    cohorts: dict[tuple[str, str, tuple[str, ...], tuple[str, ...]], _UnanchoredAliasCohort] = {}
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
        references = connector_footprint_peer_unanchored_references(divergence)
        if not references_have_current_unscoped_maps(observed, references, coverage):
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
            or len(assigned_nets) < 2
        ):
            continue
        references = connector_footprint_peer_unanchored_references(partial_open)
        if not references_have_current_unscoped_maps(observed, references, coverage):
            continue
        _cohort_for(partial_open, cohorts).partial_opens.append(partial_open)

    return tuple(
        _candidate(scan, observed, cohort, coverage) for _, cohort in sorted(cohorts.items())
    )


def _cohort_for(
    item: ConnectorFootprintPeerPinDivergence | ConnectorFootprintPeerPinOpenOutlier,
    cohorts: MutableMapping[
        tuple[str, str, tuple[str, ...], tuple[str, ...]], _UnanchoredAliasCohort
    ],
) -> _UnanchoredAliasCohort:
    """Return the bounded alias cohort owning this current scan record."""
    key = connector_footprint_peer_unanchored_cohort_key(item)
    return cohorts.setdefault(key, _UnanchoredAliasCohort(divergences=[], partial_opens=[]))


def _candidate(
    scan: ConnectorFootprintPeerPinScan,
    observed: NetlistContract,
    cohort: _UnanchoredAliasCohort,
    coverage: ConnectorCoverageReport,
) -> Candidate:
    items = (*cohort.divergences, *cohort.partial_opens)
    first = items[0]
    source_evidence = ConnectorUnanchoredPeerScopeEvidence.from_scan(
        scan=scan,
        observed=observed,
        coverage=coverage,
        divergences=tuple(cohort.divergences),
        partial_opens=tuple(cohort.partial_opens),
    )
    return ConnectorUnanchoredPeerScopeCandidate.from_source_evidence(
        source_evidence,
        subject=(
            f"{first.value} [{first.footprint}]: unanchored connector aliases lack a reviewed peer scope"
        ),
        message=(
            "Fitted connector aliases have source-matched complete pin maps and divergent generic "
            "contacts without a common-net anchor, but no reviewed peer-assignment scope. Review "
            "whether these references should be compared as peers or remain separate. A peer group "
            "only scopes comparison; it does not require matching nets or joining the contacts."
        ),
    )
