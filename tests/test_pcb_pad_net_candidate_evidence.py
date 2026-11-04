"""PCB pad-net candidates retain typed observations and source identity."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_pad_net_candidate_evidence import (
    PcbBlockedPadNetComparisonCandidate,
    PcbPadNetMismatchCandidate,
    project_blocked_pcb_pad_net_evidence,
    project_pcb_pad_net_mismatch_evidence,
)
from kicad_tooling.hwrepo.design_lint_pcb_pad_net_candidates import pcb_pad_net_candidates
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.pcb_component_inventory import (
    evaluate_native_component_inventory_coverage,
)
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
)
from tests.design_lint_fixtures.pcb_component_inventory import (
    BOARD_SHA256,
    PROBE_SHA256,
    SNAPSHOT_SHA256,
    netlist,
    snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_pad_net_finding_retains_mismatch_and_source_receipt() -> None:
    coverage = evaluate_native_component_inventory_coverage(
        netlist(components={"U1": "Synthetic:Probe"}, nets={"SCHEMATIC": ("U1.1",)}),
        snapshot(
            "U1",
            footprint_by_reference={"U1": "Synthetic:Probe"},
            pad_net_by_reference={"U1.1": "BOARD"},
        ),
        mode="review",
        pad_net_mode="review",
        netlist_sha256="a" * 64,
        board_path="projects/demo/board.kicad_pcb",
        board_sha256=BOARD_SHA256,
        snapshot_path="build/design-lint/demo.json",
        snapshot_sha256=SNAPSHOT_SHA256,
        probe_sha256=PROBE_SHA256,
    )

    (candidate,) = pcb_pad_net_candidates(coverage)

    assert isinstance(candidate, PcbPadNetMismatchCandidate)
    assert candidate.source_evidence.observation.reference == "U1"
    assert candidate.source_evidence.observation.pin == "1"
    assert candidate.source_evidence.observation.schematic_net == "SCHEMATIC"
    assert candidate.source_evidence.observation.board_net == "BOARD"
    assert candidate.source_evidence.receipt.snapshot_sha256 == SNAPSHOT_SHA256
    assert (
        candidate.evidence
        == project_pcb_pad_net_mismatch_evidence(candidate.source_evidence).evidence
    )
    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)


@pytest.mark.parametrize(
    ("report", "expected_inventory_status", "expected_issue"),
    [
        (
            PcbComponentInventoryCoverageReport(
                status="BLOCKED",
                issue="native PCB inventory unavailable",
                pad_net_comparison_status="BLOCKED",
                pad_net_comparison_issue="native PCB inventory unavailable",
            ),
            "BLOCKED",
            "native PCB inventory unavailable",
        ),
        (
            PcbComponentInventoryCoverageReport(
                status="COMPLETE",
                mode="review",
                netlist_sha256="a" * 64,
                board_path="projects/demo/board.kicad_pcb",
                board_sha256=BOARD_SHA256,
                snapshot_path="build/design-lint/demo.json",
                snapshot_sha256=SNAPSHOT_SHA256,
                snapshot_schema="12",
                kicad_version="10.0.5",
                image="registry.example/kicad:10.0.5@sha256:" + "e" * 64,
                probe_sha256=PROBE_SHA256,
                pad_net_comparison_status="BLOCKED",
                pad_net_comparison_issue="multiple electrical states for U1.1",
            ),
            "COMPLETE",
            "multiple electrical states for U1.1",
        ),
    ],
    ids=["blocked-inventory", "blocked-pad-net-only"],
)
def test_blocked_pad_net_finding_retains_both_coverage_states(
    report: PcbComponentInventoryCoverageReport,
    expected_inventory_status: str,
    expected_issue: str,
) -> None:
    (candidate,) = pcb_pad_net_candidates(report)

    assert isinstance(candidate, PcbBlockedPadNetComparisonCandidate)
    assert candidate.source_evidence.inventory_status == expected_inventory_status
    assert candidate.source_evidence.comparison_status == "BLOCKED"
    assert candidate.source_evidence.issue == expected_issue
    assert (
        candidate.evidence
        == project_blocked_pcb_pad_net_evidence(candidate.source_evidence).evidence
    )
    assert candidate.evidence["coverage_issue"] == (expected_issue,)
    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)
    if expected_inventory_status == "BLOCKED":
        assert candidate.evidence["netlist_sha256"] == ("unavailable",)
        assert candidate.evidence["snapshot_sha256"] == ("unavailable",)
    else:
        assert candidate.evidence["netlist_sha256"] == ("a" * 64,)
        assert candidate.evidence["snapshot_sha256"] == (SNAPSHOT_SHA256,)
