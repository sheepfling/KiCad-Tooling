"""Source-bound regressions for named connector contacts left open on peers."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.connector_coverage import (
    source_matched_connector_peer_assignment_groups,
)
from kicad_tooling.hwrepo.design_lint_connector_footprint_candidates import (
    connector_footprint_peer_pin_candidates,
)
from kicad_tooling.hwrepo.design_lint_connector_footprint_named_open_evidence import (
    ConnectorNamedOpenCandidate,
    project_connector_named_open_evidence,
)
from tests.connector_footprint_peer_support import peer_netlist
from tests.connector_peer_unanchored_scope_support import reviewed_coverage

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.evidence_lint,
]

RULE_ID = "connector.footprint_named_signal_output_open_outlier"


def _candidate() -> ConnectorNamedOpenCandidate:
    observed = peer_netlist(
        assignments=(("GND", "GND"), ("DATA_A", None)),
        functions=("GND", "TXD"),
        electrical_types=("passive", "output"),
    )
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
    assert isinstance(candidate, ConnectorNamedOpenCandidate)
    return candidate


def test_named_open_candidate_retains_current_scan_coverage_and_projection() -> None:
    candidate = _candidate()

    assert candidate.source_evidence.coverage is not None
    assert candidate.source_evidence.item.open_pins == ("J2.2",)
    assert candidate.evidence["assignments"] == ("J1.2=DATA_A", "J2.2=<unassigned>")
    assert (
        candidate.evidence
        == project_connector_named_open_evidence(candidate.source_evidence).evidence
    )


def test_named_open_evidence_rejects_an_assignment_changed_after_the_scan() -> None:
    source = _candidate().source_evidence
    changed = source.scan.source.observed.model_copy(
        update={
            "nets": {
                "GND": ("J1.1", "J2.1"),
                "DATA_A": ("J1.2",),
                "DATA_B": ("J2.2",),
            }
        }
    )
    changed_scan = replace(source.scan, source=replace(source.scan.source, observed=changed))

    with pytest.raises(ValueError, match="source-matched peer groups|current peer scan"):
        replace(source, scan=changed_scan)


def test_named_open_evidence_rejects_coverage_with_a_changed_peer_group() -> None:
    source = _candidate().source_evidence
    assert source.coverage is not None
    entries = tuple(
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
    changed_coverage = source.coverage.model_copy(update={"entries": entries})

    with pytest.raises(ValueError, match="source-matched peer groups"):
        replace(source, coverage=changed_coverage)


def test_named_open_candidate_rejects_changed_projection_fields() -> None:
    candidate = _candidate()
    changed_evidence = dict(candidate.evidence)
    changed_evidence["open_pins"] = ("J1.2",)

    with pytest.raises(ValueError, match="source projection"):
        replace(candidate, evidence=changed_evidence)
