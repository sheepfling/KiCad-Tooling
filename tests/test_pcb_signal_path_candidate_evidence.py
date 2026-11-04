"""Typed source and wire projection for signal-path coverage findings."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_requirement_candidates import (
    pcb_requirement_coverage_candidates,
)
from kicad_tooling.hwrepo.design_lint_pcb_signal_path_coverage_evidence import (
    PcbSignalPathCoverageCandidate,
    PcbSignalPathCoverageFindingEvidence,
    project_pcb_signal_path_coverage_evidence,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from tests.design_lint_fixtures.pcb_signal_path import incomplete_signal_report, path_map

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]


def test_signal_path_candidate_retains_report_and_preserves_fingerprint() -> None:
    report = incomplete_signal_report(path_map())
    (candidate,) = pcb_requirement_coverage_candidates(pcb_signal_path_coverage=report)

    assert isinstance(candidate, PcbSignalPathCoverageCandidate)
    assert candidate.source_evidence.report == report
    assert candidate.source_evidence.entry == report.entries[0]
    assert (
        candidate.evidence
        == project_pcb_signal_path_coverage_evidence(candidate.source_evidence).evidence
    )

    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)


def test_signal_path_finding_rejects_non_incomplete_report() -> None:
    report = incomplete_signal_report(path_map())
    complete_report = report.model_copy(update={"status": "COMPLETE"})

    with pytest.raises(ValueError, match="requires INCOMPLETE report"):
        PcbSignalPathCoverageFindingEvidence(report=complete_report, entry=report.entries[0])
