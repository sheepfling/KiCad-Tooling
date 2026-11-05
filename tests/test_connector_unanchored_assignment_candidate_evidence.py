"""Source-bound regressions for reviewed unanchored connector assignments."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.connector_coverage import (
    source_matched_connector_peer_assignment_groups,
)
from kicad_tooling.hwrepo.connector_footprint_peer_unanchored_divergence import (
    reviewed_unanchored_connector_alias_divergences,
)
from kicad_tooling.hwrepo.design_lint_connector_footprint_candidates import (
    connector_footprint_peer_pin_candidates,
)
from kicad_tooling.hwrepo.design_lint_connector_unanchored_assignment_evidence import (
    ConnectorUnanchoredAssignmentCandidate,
    project_connector_unanchored_assignment_evidence,
)
from tests.connector_footprint_peer_support import peer_netlist
from tests.connector_peer_unanchored_scope_support import PEER_GROUP, reviewed_coverage

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.evidence_lint,
]

RULE_ID = "connector.footprint_peer_pin_unanchored_assignment_divergence"


def _candidate() -> ConnectorUnanchoredAssignmentCandidate:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    coverage = reviewed_coverage(observed)
    candidates = connector_footprint_peer_pin_candidates(
        observed,
        peer_assignment_groups=source_matched_connector_peer_assignment_groups(
            observed,
            coverage,
        ),
        connector_coverage=coverage,
    )
    candidate = next(item for item in candidates if item.rule_id == RULE_ID)
    assert isinstance(candidate, ConnectorUnanchoredAssignmentCandidate)
    return candidate


def test_reviewed_assignment_candidate_retains_current_scan_and_coverage() -> None:
    candidate = _candidate()

    assert candidate.source_evidence.coverage is not None
    assert candidate.source_evidence.scan.source.peer_assignment_groups is not None
    assert (
        candidate.evidence
        == project_connector_unanchored_assignment_evidence(candidate.source_evidence).evidence
    )
    assert candidate.evidence["assignments"] == ("J1.1=PORT_A", "J2.1=PORT_B")
    assert candidate.evidence["peer_assignment_group"] == (PEER_GROUP,)


def test_reviewed_assignment_evidence_rejects_mappings_stale_for_changed_netlist() -> None:
    source = _candidate().source_evidence
    changed = source.scan.source.observed.model_copy(
        update={"nets": {"PORT_A": ("J1.1",), "PORT_B": ("J2.1",)}}
    )
    changed_scan = replace(source.scan, source=replace(source.scan.source, observed=changed))

    with pytest.raises(ValueError, match="source-matched peer groups"):
        replace(source, scan=changed_scan)


def test_reviewed_assignment_evidence_rejects_a_changed_review_basis() -> None:
    source = _candidate().source_evidence
    changed_entries = tuple(
        entry.model_copy(
            update={
                "peer_assignment_group": "Different reviewed peers",
                "peer_assignment_basis": "Changed review basis",
            }
        )
        if entry.reference in {"J1", "J2"}
        else entry
        for entry in source.coverage.entries
    )
    changed_coverage = source.coverage.model_copy(update={"entries": changed_entries})

    with pytest.raises(ValueError, match="source-matched peer groups"):
        replace(source, coverage=changed_coverage)


def test_reviewed_assignment_adapter_requires_the_coverage_report() -> None:
    candidate = _candidate()

    assert not reviewed_unanchored_connector_alias_divergences(candidate.source_evidence.scan)


def test_reviewed_assignment_candidate_rejects_changed_projection_fields() -> None:
    candidate = _candidate()
    changed_evidence = dict(candidate.evidence)
    changed_evidence["assignments"] = ("J1.1=OTHER", "J2.1=OTHER")

    with pytest.raises(ValueError, match="source projection"):
        replace(candidate, evidence=changed_evidence)
