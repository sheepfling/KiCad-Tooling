"""Build review findings for eligible named contacts open across aliases."""

from __future__ import annotations

from .connector_coverage_models import ConnectorCoverageReport
from .connector_footprint_peer_pin_types import (
    ConnectorFootprintPeerPinOpenOutlier,
    ConnectorFootprintPeerPinScan,
)
from .design_lint_connector_footprint_named_open_evidence import (
    ConnectorNamedOpenCandidate,
    ConnectorNamedOpenEvidence,
    ConnectorNamedOpenRuleId,
)
from .design_lint_types import Candidate


def open_named_outlier_candidates(
    scan: ConnectorFootprintPeerPinScan,
    records: tuple[ConnectorFootprintPeerPinOpenOutlier, ...],
    *,
    coverage: ConnectorCoverageReport | None,
    rule_id: ConnectorNamedOpenRuleId,
) -> tuple[Candidate, ...]:
    """Convert classified open-peer records into named-contact review candidates."""
    candidates = tuple(
        ConnectorNamedOpenCandidate.from_source_evidence(
            ConnectorNamedOpenEvidence.from_scan(
                scan=scan,
                coverage=coverage,
                item=item,
                rule_id=rule_id,
            )
        )
        for item in records
    )
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.subject.casefold(),
                candidate.subject,
                tuple(sorted(candidate.evidence)),
            ),
        )
    )
