"""PCB population findings retain typed mismatches and explicit coverage state."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_component_inventory_candidates import (
    pcb_component_inventory_candidates,
)
from kicad_tooling.hwrepo.design_lint_pcb_population_candidate_evidence import (
    PcbBlockedVariantPopulationCandidate,
    PcbBlockedVariantPopulationEvidence,
    PcbPopulationCandidate,
    project_blocked_variant_population_evidence,
    project_pcb_population_evidence,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbPopulationMismatch,
    PcbVariantPopulationCoverage,
    PcbVariantPopulationEvidence,
)
from tests.design_lint_fixtures.pcb_component_inventory import (
    BOARD_SHA256,
    IMAGE,
    SNAPSHOT_SHA256,
    complete_report,
    netlist,
    snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]
RULE_ID = "pcb.schematic_pcb_dnp_mismatch"


def test_population_mismatch_retains_source_and_public_fingerprint() -> None:
    observed = netlist(components={"U1": "Synthetic:Probe_Module"})
    report = complete_report(
        observed,
        snapshot(
            "U1",
            footprint_by_reference={"U1": "Synthetic:Probe_Module"},
            dnp_by_reference={"U1": True},
        ),
    )

    (candidate,) = tuple(
        item for item in pcb_component_inventory_candidates(report) if item.rule_id == RULE_ID
    )

    assert isinstance(candidate, PcbPopulationCandidate)
    assert candidate.source_evidence.observation == PcbPopulationMismatch(
        reference="U1",
        schematic_dnp=False,
        board_dnp=True,
    )
    assert candidate.source_evidence.receipt.board_sha256 == BOARD_SHA256
    assert candidate.source_evidence.receipt.snapshot_sha256 == SNAPSHOT_SHA256
    assert candidate.evidence == project_pcb_population_evidence(candidate.source_evidence).evidence

    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)


def test_named_variant_mismatch_retains_its_paired_export_source() -> None:
    observed = netlist(components={"U1": "Synthetic:Probe_Module"})
    report = complete_report(
        observed,
        snapshot("U1", footprint_by_reference={"U1": "Synthetic:Probe_Module"}),
    ).model_copy(
        update={
            "population_mismatches": (
                PcbPopulationMismatch(
                    reference="U1",
                    schematic_dnp=False,
                    board_dnp=True,
                    variant="Assembly A",
                ),
            ),
            "variant_population": PcbVariantPopulationCoverage(
                status="COMPLETE",
                project_path="projects/synthetic/controller.kicad_pro",
                project_sha256="1" * 64,
                schematic_path="projects/synthetic/controller.kicad_sch",
                schematic_sha256="2" * 64,
                board_path="projects/synthetic/controller.kicad_pcb",
                board_sha256=BOARD_SHA256,
                kicad_version="10.0.5",
                image=IMAGE,
                board_variant_probe_path="build/design-lint/variant/probe.py",
                board_variant_probe_sha256="3" * 64,
                board_variant_request_path="build/design-lint/variant/request.json",
                board_variant_request_sha256="4" * 64,
                board_variant_command_path="build/design-lint/variant/probe.command.json",
                board_variant_command_sha256="5" * 64,
                evidence=(
                    PcbVariantPopulationEvidence(
                        variant="Assembly A",
                        netlist_path="build/design-lint/variant/variant.netlist.xml",
                        netlist_sha256="6" * 64,
                        netlist_command_path="build/design-lint/variant/netlist.command.json",
                        netlist_command_sha256="7" * 64,
                        board_all_positions_path="build/design-lint/variant/board-all.csv",
                        board_all_positions_sha256="8" * 64,
                        board_all_command_path="build/design-lint/variant/board-all.command.json",
                        board_all_command_sha256="9" * 64,
                        board_fitted_positions_path="build/design-lint/variant/board-fitted.csv",
                        board_fitted_positions_sha256="a" * 64,
                        board_fitted_command_path="build/design-lint/variant/board-fitted.command.json",
                        board_fitted_command_sha256="b" * 64,
                    ),
                ),
            ),
        }
    )

    (candidate,) = tuple(
        item for item in pcb_component_inventory_candidates(report) if item.rule_id == RULE_ID
    )

    assert isinstance(candidate, PcbPopulationCandidate)
    assert candidate.source_evidence.observation.variant == "Assembly A"
    assert candidate.evidence["variant_netlist_sha256"] == ("6" * 64,)
    assert candidate.evidence == project_pcb_population_evidence(candidate.source_evidence).evidence
    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)


def test_blocked_variant_finding_retains_blocked_coverage_without_promoting_it() -> None:
    report = complete_report(
        netlist(components={"U1": "Synthetic:Probe_Module"}),
        snapshot("U1", footprint_by_reference={"U1": "Synthetic:Probe_Module"}),
    ).model_copy(
        update={
            "variant_population": PcbVariantPopulationCoverage(
                status="BLOCKED",
                project_path="projects/synthetic/controller.kicad_pro",
                project_sha256="1" * 64,
                board_path="projects/synthetic/controller.kicad_pcb",
                board_sha256=BOARD_SHA256,
                kicad_version="10.0.5",
                image=IMAGE,
                issue="PCB source does not contain the declared named variant",
            )
        }
    )

    (candidate,) = tuple(
        item
        for item in pcb_component_inventory_candidates(report)
        if item.subject == "named variant DNP comparison unavailable"
    )

    assert isinstance(candidate, PcbBlockedVariantPopulationCandidate)
    assert candidate.source_evidence.coverage.status == "BLOCKED"
    assert candidate.evidence["coverage_issue"] == (
        "PCB source does not contain the declared named variant",
    )
    assert (
        candidate.evidence
        == project_blocked_variant_population_evidence(candidate.source_evidence).evidence
    )
    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)


def test_blocked_variant_source_rejects_complete_coverage() -> None:
    with pytest.raises(ValueError, match="requires BLOCKED coverage"):
        PcbBlockedVariantPopulationCandidate.from_source_evidence(
            source_evidence=PcbBlockedVariantPopulationEvidence(
                PcbVariantPopulationCoverage(status="NOT_APPLICABLE")
            ),
            subject="unavailable",
            message="unavailable",
        )
