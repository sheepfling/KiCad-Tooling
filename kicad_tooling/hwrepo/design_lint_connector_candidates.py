"""Coordinate connector pin and return-domain lint candidates."""

from __future__ import annotations

from .design_lint_connector_pin_candidates import connector_pin_candidates
from .design_lint_return_domain_candidates import return_domain_candidates
from .design_lint_types import Candidate
from .models import ConnectorCoverageReport, NetlistContract


def connector_candidates(
    observed: NetlistContract,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Collect connector pin findings followed by return-domain review prompts."""
    return (
        *connector_pin_candidates(
            observed,
            connector_coverage=connector_coverage,
            reviewed_connector_references=reviewed_connector_references,
        ),
        *return_domain_candidates(
            observed,
            connector_coverage=connector_coverage,
            reviewed_connector_references=reviewed_connector_references,
        ),
    )
