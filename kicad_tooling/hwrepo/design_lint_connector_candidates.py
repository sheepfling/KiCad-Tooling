"""Coordinate connector pin and return-domain lint candidates."""

from __future__ import annotations

from .connector_coverage import source_matched_connector_peer_assignment_groups
from .connector_coverage_models import ConnectorCoverageReport
from .connector_peer_pin_candidate_results import (
    ConnectorCandidateResult,
    ConnectorPeerPinFindingCounts,
)
from .connector_scope_coverage_candidates import connector_scope_singleton_candidates
from .connector_stateful_contact_models import ConnectorStatefulContactMap
from .connector_stateful_contacts import stateful_connector_contact_findings
from .design_lint_connector_footprint_candidates import (
    connector_footprint_peer_pin_candidates,
)
from .design_lint_connector_pin_candidates import connector_pin_candidates
from .design_lint_connectors_supply_domains import (
    mapped_supply_domains_shared_net_candidates,
)
from .design_lint_return_domain_candidates import return_domain_candidates
from .design_lint_types import Candidate
from .models import NetlistContract


def connector_candidates(
    observed: NetlistContract,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
    power_output_review_enabled: bool = True,
    stateful_contact_map: ConnectorStatefulContactMap | None = None,
) -> tuple[Candidate, ...]:
    """Collect connector pin findings followed by return-domain review prompts."""
    return (
        *connector_pin_candidates(
            observed,
            connector_coverage=connector_coverage,
            reviewed_connector_references=reviewed_connector_references,
            power_output_review_enabled=power_output_review_enabled,
        ),
        *mapped_supply_domains_shared_net_candidates(observed, connector_coverage),
        *connector_scope_singleton_candidates(observed, connector_coverage),
        *connector_footprint_peer_pin_candidates(
            observed,
            reviewed_connector_references,
            source_matched_connector_peer_assignment_groups(observed, connector_coverage),
            connector_coverage,
        ),
        *return_domain_candidates(
            observed,
            connector_coverage=connector_coverage,
            reviewed_connector_references=reviewed_connector_references,
        ),
        *stateful_connector_contact_findings(observed, stateful_contact_map),
    )


def scan_connector_candidates(
    observed: NetlistContract,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
    power_output_review_enabled: bool = True,
    stateful_contact_map: ConnectorStatefulContactMap | None = None,
) -> ConnectorCandidateResult:
    """Return connector findings with the summary needed by peer-pin coverage."""
    found = connector_candidates(
        observed,
        connector_coverage=connector_coverage,
        reviewed_connector_references=reviewed_connector_references,
        power_output_review_enabled=power_output_review_enabled,
        stateful_contact_map=stateful_contact_map,
    )
    return ConnectorCandidateResult(
        candidates=found,
        peer_pin_finding_counts=ConnectorPeerPinFindingCounts.from_candidates(found),
    )
