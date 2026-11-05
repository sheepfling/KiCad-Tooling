"""Source-bound regressions for connector findings with incomplete coverage."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.connector_footprint_peer_pins import (
    scan_connector_footprint_peer_pin_assignments,
)
from kicad_tooling.hwrepo.connector_footprint_peer_unanchored_coverage_review import (
    uncovered_unanchored_connector_alias_scope,
)
from kicad_tooling.hwrepo.design_lint_connector_unanchored_coverage_evidence import (
    ConnectorUnanchoredCoverageCandidate,
    project_connector_unanchored_coverage_evidence,
)
from tests.connector_footprint_peer_support import peer_netlist
from tests.connector_peer_unanchored_scope_support import reviewed_coverage

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]


def _candidate(
    *,
    assignments: tuple[tuple[str | None, str | None], ...] = (
        ("PORT_A", "PORT_B"),
        ("DATA_A", "DATA_B"),
    ),
    coverage: ConnectorCoverageReport | None = None,
) -> ConnectorUnanchoredCoverageCandidate:
    observed = peer_netlist(assignments=assignments)
    scan = scan_connector_footprint_peer_pin_assignments(observed)
    candidates = uncovered_unanchored_connector_alias_scope(scan, coverage)
    assert candidates
    candidate = candidates[0]
    assert isinstance(candidate, ConnectorUnanchoredCoverageCandidate)
    return candidate


def test_coverage_candidate_keeps_exact_optional_report_and_projection() -> None:
    candidate = _candidate()

    assert candidate.source_evidence.coverage is None
    assert candidate.evidence["coverage_status"] == ("NOT_SUPPLIED",)
    assert (
        candidate.evidence
        == project_connector_unanchored_coverage_evidence(candidate.source_evidence).evidence
    )


def test_coverage_candidate_rejects_a_changed_native_assignment_source() -> None:
    source = _candidate().source_evidence
    changed = source.scan.source.observed.model_copy(
        update={"nets": {"PORT_A": ("J1.1",), "PORT_B": ("J2.1",)}}
    )
    changed_scan = replace(source.scan, source=replace(source.scan.source, observed=changed))

    with pytest.raises(ValueError, match="assignments|current native scan"):
        replace(source, scan=changed_scan)


def test_covered_entries_must_still_match_the_current_netlist() -> None:
    original = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    source_coverage = reviewed_coverage(original, (None, None))
    incomplete_coverage = source_coverage.model_copy(update={"status": "INCOMPLETE"})
    changed = original.model_copy(
        update={
            "nets": {
                "PORT_A": ("J1.1",),
                "PORT_B": ("J2.1",),
                "DATA_C": ("J2.2",),
                "DATA_A": ("J1.2",),
            }
        }
    )
    changed_scan = scan_connector_footprint_peer_pin_assignments(changed)

    with pytest.raises(ValueError, match="source-matched pin maps"):
        uncovered_unanchored_connector_alias_scope(changed_scan, incomplete_coverage)
