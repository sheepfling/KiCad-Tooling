"""Review unanchored connector alias splits when comparison scope is absent."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from .connector_coverage_models import ConnectorCoverageReport
from .connector_footprint_peer_pin_types import (
    ConnectorFootprintPeerPinDivergence,
    ConnectorFootprintPeerPinScan,
)
from .connector_identity import pin_function_is_generic
from .design_lint_connector_unanchored_scope_evidence import (
    ConnectorUnanchoredPeerScopeCandidate,
    ConnectorUnanchoredPeerScopeEvidence,
    references_have_current_unscoped_maps,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract


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
        if not references_have_current_unscoped_maps(observed, references, coverage):
            continue
        cohort_key = (
            divergence.value.casefold(),
            divergence.footprint.casefold(),
            tuple(reference.casefold() for reference in references),
            tuple(symbol.casefold() for symbol in divergence.symbols),
        )
        cohorts[cohort_key].append(divergence)

    return tuple(
        _candidate(scan, observed, divergences, coverage)
        for _, divergences in sorted(cohorts.items())
    )


def _candidate(
    scan: ConnectorFootprintPeerPinScan,
    observed: NetlistContract,
    divergences: Sequence[ConnectorFootprintPeerPinDivergence],
    coverage: ConnectorCoverageReport,
) -> Candidate:
    first = divergences[0]
    source_evidence = ConnectorUnanchoredPeerScopeEvidence.from_scan(
        scan=scan,
        observed=observed,
        coverage=coverage,
        divergences=tuple(divergences),
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
