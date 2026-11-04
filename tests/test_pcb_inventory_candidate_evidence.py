"""PCB footprint findings retain the typed comparison and native source receipt."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_component_inventory_candidates import (
    pcb_component_inventory_candidates,
)
from kicad_tooling.hwrepo.design_lint_pcb_inventory_candidate_evidence import (
    PcbInventoryCandidate,
    project_pcb_inventory_evidence,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
)
from tests.design_lint_fixtures.pcb_component_inventory import (
    complete_report,
    netlist,
    snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


@pytest.mark.parametrize(
    ("report", "expected_assigned", "expected_placed"),
    [
        (
            complete_report(
                netlist(components={"U1": "Package_QFP:TQFP-48"}),
                snapshot(),
            ),
            "Package_QFP:TQFP-48",
            None,
        ),
        (
            complete_report(
                netlist(components={"U1": "Package_SO:SOIC-8"}),
                snapshot("u1", footprint_by_reference={"U1": "Package_TSSOP:TSSOP-8"}),
            ),
            "Package_SO:SOIC-8",
            "Package_TSSOP:TSSOP-8",
        ),
    ],
    ids=["missing-placement", "identity-mismatch"],
)
def test_footprint_candidate_retains_source_and_preserves_public_fingerprint(
    report: PcbComponentInventoryCoverageReport,
    expected_assigned: str,
    expected_placed: str | None,
) -> None:
    (candidate,) = pcb_component_inventory_candidates(report)

    assert isinstance(candidate, PcbInventoryCandidate)
    assert candidate.source_evidence.observation.reference == "U1"
    assert candidate.source_evidence.receipt.snapshot_sha256 is not None
    assert candidate.source_evidence.receipt.board_path is not None
    assert candidate.evidence == project_pcb_inventory_evidence(candidate.source_evidence).evidence
    assert candidate.evidence["assigned_footprint"] == (expected_assigned,)
    if expected_placed is not None:
        assert candidate.evidence["placed_footprint"] == (expected_placed,)
    assert candidate.evidence["snapshot_sha256"] == (
        candidate.source_evidence.receipt.snapshot_sha256,
    )

    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)
