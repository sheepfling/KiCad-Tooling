"""Typed PCB requirement candidates retain the source reports behind findings."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_keepout_candidate_evidence import PcbKeepoutCandidate
from kicad_tooling.hwrepo.design_lint_pcb_requirement_candidates import (
    pcb_requirement_coverage_candidates,
)
from kicad_tooling.hwrepo.design_lint_pcb_rf_antenna_candidate_evidence import (
    PcbRfAntennaCandidate,
)
from kicad_tooling.hwrepo.design_lint_pcb_switching_loop_candidate_evidence import (
    PcbSwitchingLoopCandidate,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import DesignLintPolicy, PcbRfModuleAntennaMap
from tests.design_lint_fixtures.pcb_switching_loop_reports import coverage as switching_coverage
from tests.design_lint_fixtures.pcb_switching_loop_routes import routed_mapping, routed_snapshot
from tests.pcb_rf_antenna_support import lint_report, netlist, requirement, snapshot
from tests.test_pcb_keepouts import incomplete_report as incomplete_keepout_report

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]


def _assert_public_fingerprint(candidate: Candidate) -> None:
    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)


def test_switching_loop_candidate_retains_measurement_and_source_report() -> None:
    mapping = routed_mapping()
    report = switching_coverage(mapping, routed_snapshot(disconnected=True))
    (candidate,) = pcb_requirement_coverage_candidates(pcb_switching_loop_coverage=report)

    assert isinstance(candidate, PcbSwitchingLoopCandidate)
    assert candidate.source_evidence.report == report
    assert candidate.source_evidence.entry == report.entries[0]
    assert candidate.evidence["coverage_status"] == (report.entries[0].status,)
    assert candidate.evidence["maximum_area_um2"] == (str(report.entries[0].maximum_area_um2),)
    assert candidate.evidence["return_net"] == (report.entries[0].return_net,)
    assert candidate.evidence["issues"] == report.entries[0].issues
    _assert_public_fingerprint(candidate)


def test_keepout_candidate_retains_signature_comparison_and_source_report() -> None:
    report = incomplete_keepout_report()
    (candidate,) = pcb_requirement_coverage_candidates(pcb_keepout_coverage=report)

    assert isinstance(candidate, PcbKeepoutCandidate)
    assert candidate.source_evidence.report == report
    assert candidate.source_evidence.entry == report.entries[0]
    assert set(candidate.evidence) == {
        "basis",
        "expected_geometry_sha256",
        "observed_geometry_sha256",
        "expected_layers",
        "observed_layers",
        "observed_restrictions",
        "issues",
    }
    assert candidate.evidence["issues"] == report.entries[0].issues
    _assert_public_fingerprint(candidate)


def test_rf_antenna_candidate_retains_module_comparison_and_source_report() -> None:
    antenna_map = PcbRfModuleAntennaMap(
        basis="Synthetic RF module review",
        requirements=(requirement(),),
    )
    report = lint_report(
        policy=DesignLintPolicy(pcb_rf_module_antenna_map=antenna_map),
        source_netlist=netlist(),
        observed_board=snapshot(pad_net="RF_OUT"),
    ).pcb_rf_module_antenna_coverage
    (candidate,) = pcb_requirement_coverage_candidates(pcb_rf_module_antenna_coverage=report)

    assert isinstance(candidate, PcbRfAntennaCandidate)
    assert candidate.source_evidence.report == report
    assert candidate.source_evidence.entry == report.entries[0]
    assert candidate.evidence["expected_rf_feed_net"] == ("RF_IN",)
    assert candidate.evidence["observed_board_rf_feed_net"] == ("RF_OUT",)
    assert candidate.evidence["issues"] == report.entries[0].issues
    _assert_public_fingerprint(candidate)
