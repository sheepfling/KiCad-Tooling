"""Blocked PCB value findings retain explicit source and coverage state."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_component_inventory_candidates import (
    pcb_component_inventory_candidates,
)
from kicad_tooling.hwrepo.design_lint_pcb_value_candidate_evidence import (
    PcbBlockedValueComparisonCandidate,
    PcbValueMismatchCandidate,
    project_blocked_value_comparison_evidence,
    project_pcb_value_mismatch_evidence,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbComponentValueMismatch,
)
from tests.design_lint_fixtures.pcb_component_inventory import (
    complete_report,
    netlist,
    snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]
RULE_ID = "pcb.schematic_pcb_value_mismatch"
FOOTPRINT = "Synthetic:Probe_Module"


def test_complete_value_candidates_keep_typed_base_and_variant_sources() -> None:
    report = complete_report(
        netlist(components={"R1": FOOTPRINT}, values={"R1": "10k"}),
        snapshot(
            "R1",
            schema_version="13",
            footprint_by_reference={"R1": FOOTPRINT},
            value_by_reference={"R1": "10K"},
        ),
        value_mode="review",
    )
    variant_report = report.model_copy(
        update={
            "value_mismatches": (
                PcbComponentValueMismatch(
                    reference="R1",
                    schematic_value="10k",
                    board_value="10K",
                    variant="Assembly A",
                ),
            )
        }
    )

    (base_candidate,) = tuple(
        item for item in pcb_component_inventory_candidates(report) if item.rule_id == RULE_ID
    )
    (variant_candidate,) = tuple(
        item
        for item in pcb_component_inventory_candidates(variant_report)
        if item.rule_id == RULE_ID
    )

    for candidate in (base_candidate, variant_candidate):
        assert isinstance(candidate, PcbValueMismatchCandidate)
        assert (
            candidate.evidence
            == project_pcb_value_mismatch_evidence(candidate.source_evidence).evidence
        )
        assert fingerprint(candidate) == fingerprint(
            Candidate(
                rule_id=candidate.rule_id,
                subject=candidate.subject,
                message=candidate.message,
                evidence=candidate.evidence,
            )
        )
    assert isinstance(base_candidate, PcbValueMismatchCandidate)
    assert isinstance(variant_candidate, PcbValueMismatchCandidate)
    assert base_candidate.source_evidence.observation.variant is None
    assert variant_candidate.source_evidence.observation.variant == "Assembly A"
    assert variant_candidate.evidence["variant_evidence"] == ("unavailable",)


def test_blocked_value_comparison_retains_complete_inventory_source_state() -> None:
    report = complete_report(
        netlist(components={"R1": FOOTPRINT}, values={"R1": "10k"}),
        snapshot(
            "R1",
            schema_version="12",
            footprint_by_reference={"R1": FOOTPRINT},
        ),
        value_mode="review",
    )

    (candidate,) = tuple(
        item for item in pcb_component_inventory_candidates(report) if item.rule_id == RULE_ID
    )

    assert isinstance(candidate, PcbBlockedValueComparisonCandidate)
    assert candidate.source_evidence.inventory_status == "COMPLETE"
    assert candidate.source_evidence.coverage_status == "BLOCKED"
    assert (
        candidate.evidence
        == project_blocked_value_comparison_evidence(candidate.source_evidence).evidence
    )
    assert candidate.evidence["snapshot_schema"] == ("12",)


def test_blocked_inventory_value_finding_preserves_sparse_evidence() -> None:
    report = PcbComponentInventoryCoverageReport(
        status="BLOCKED",
        issue="native inventory unavailable",
        value_comparison_status="BLOCKED",
        value_comparison_issue="native value export unavailable",
    )

    (candidate,) = tuple(
        item for item in pcb_component_inventory_candidates(report) if item.rule_id == RULE_ID
    )

    assert isinstance(candidate, PcbBlockedValueComparisonCandidate)
    assert candidate.source_evidence.inventory_status == "BLOCKED"
    assert candidate.source_evidence.issue == "native value export unavailable"
    assert (
        candidate.evidence
        == project_blocked_value_comparison_evidence(candidate.source_evidence).evidence
    )
    assert candidate.evidence == {
        "coverage_issue": ("native value export unavailable",),
        "netlist_sha256": (),
        "board_path": (),
        "board_sha256": (),
        "snapshot_sha256": (),
        "snapshot_schema": (),
    }
