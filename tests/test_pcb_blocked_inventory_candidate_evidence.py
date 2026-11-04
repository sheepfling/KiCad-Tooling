"""Blocked PCB inventory findings retain their typed coverage source."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_blocked_inventory_evidence import (
    PcbBlockedComponentInventoryCandidate,
    PcbBlockedComponentInventoryEvidence,
    PcbBlockedPopulationCandidate,
    project_blocked_component_inventory_evidence,
    project_blocked_population_evidence,
)
from kicad_tooling.hwrepo.design_lint_pcb_component_inventory_candidates import (
    pcb_component_inventory_candidates,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_blocked_inventory_candidates_preserve_typed_report_and_wire_fields() -> None:
    report = PcbComponentInventoryCoverageReport(
        status="BLOCKED",
        issue="native board snapshot unavailable",
        netlist_sha256="a" * 64,
        board_path="projects/demo/board.kicad_pcb",
        board_sha256="b" * 64,
        snapshot_sha256="c" * 64,
    )

    inventory_candidate, population_candidate = pcb_component_inventory_candidates(report)

    assert isinstance(inventory_candidate, PcbBlockedComponentInventoryCandidate)
    assert isinstance(population_candidate, PcbBlockedPopulationCandidate)
    assert inventory_candidate.source_evidence == population_candidate.source_evidence
    source = PcbBlockedComponentInventoryEvidence(report)
    assert inventory_candidate.source_evidence == source
    assert source.report.status == "BLOCKED"
    assert (
        inventory_candidate.evidence
        == project_blocked_component_inventory_evidence(source).evidence
    )
    assert population_candidate.evidence == project_blocked_population_evidence(source).evidence
    assert inventory_candidate.evidence == {
        "coverage_issue": ("native board snapshot unavailable",),
        "netlist_sha256": ("a" * 64,),
        "board_path": ("projects/demo/board.kicad_pcb",),
        "board_sha256": ("b" * 64,),
    }
    assert population_candidate.evidence == {
        "coverage_issue": ("native board snapshot unavailable",),
        "netlist_sha256": ("a" * 64,),
        "board_path": ("projects/demo/board.kicad_pcb",),
        "board_sha256": ("b" * 64,),
        "snapshot_sha256": ("c" * 64,),
    }
    for candidate in (inventory_candidate, population_candidate):
        public_candidate = Candidate(
            rule_id=candidate.rule_id,
            subject=candidate.subject,
            message=candidate.message,
            evidence=candidate.evidence,
        )
        assert fingerprint(candidate) == fingerprint(public_candidate)


def test_blocked_inventory_candidates_preserve_empty_optional_fields() -> None:
    (inventory_candidate, population_candidate) = pcb_component_inventory_candidates(
        PcbComponentInventoryCoverageReport(
            status="BLOCKED",
            issue="board path is unavailable",
        )
    )

    assert inventory_candidate.evidence == {
        "coverage_issue": ("board path is unavailable",),
        "netlist_sha256": (),
        "board_path": (),
        "board_sha256": (),
    }
    assert population_candidate.evidence == {
        "coverage_issue": ("board path is unavailable",),
        "netlist_sha256": (),
        "board_path": (),
        "board_sha256": (),
        "snapshot_sha256": (),
    }


def test_blocked_inventory_source_rejects_non_blocked_report() -> None:
    with pytest.raises(ValueError, match="requires BLOCKED status"):
        PcbBlockedComponentInventoryEvidence(
            PcbComponentInventoryCoverageReport(status="NOT_APPLICABLE")
        )
