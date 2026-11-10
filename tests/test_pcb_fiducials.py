"""Deterministic, authored PCB fiducial count checks."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_fiducial_scan import normalize_pcb_fiducial_coverage
from kicad_tooling.hwrepo.design_lint_pcb_report import pcb_coverage_report_lines
from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_fiducial_models import PcbFiducialCoverageReport
from kicad_tooling.hwrepo.pcb_fiducials import evaluate_pcb_fiducials, pcb_fiducial_entries
from tests.design_lint_fixtures.pcb_component_inventory import (
    BOARD_SHA256 as INVENTORY_BOARD_SHA256,
)
from tests.design_lint_fixtures.pcb_component_inventory import (
    NETLIST_SHA256,
    coach,
    complete_report,
    netlist,
)
from tests.pcb_fiducials_support import (
    BOARD_PATH,
    BOARD_SHA256,
    FIDUCIAL_FOOTPRINT,
    requirement_map,
    snapshot,
    source_evidence,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]
RULE = "pcb.fiducial_count"


def test_exact_footprint_identity_and_side_control_the_fiducial_count() -> None:
    authored = requirement_map(minimum=2, side="front")
    (entry,) = pcb_fiducial_entries(authored, source_evidence())

    assert entry.status == "INCOMPLETE"
    assert entry.observed_count == 1
    assert tuple(item.reference for item in entry.observations) == ("FID1",)
    assert entry.accepted_footprints == (FIDUCIAL_FOOTPRINT,)
    assert entry.issues == ("Found 1 fitted board fiducial footprints; 2 required",)


def test_either_side_counts_fitted_exact_matches_and_excludes_dnp_and_other_parts() -> None:
    (entry,) = pcb_fiducial_entries(requirement_map(side="either"), source_evidence())

    assert entry.status == "COMPLETE"
    assert entry.observed_count == 2
    assert tuple(item.reference for item in entry.observations) == ("FID1", "FID2")


def test_footprint_identifier_match_ignores_case_but_not_partial_names() -> None:
    board = snapshot(
        (
            ("FID1", "synthetic:fiducial_1mm_mask2mm", False, "F.Cu"),
            ("FID2", "Synthetic:Fiducial_1mm", False, "F.Cu"),
        )
    )
    (entry,) = pcb_fiducial_entries(
        requirement_map(minimum=1, side="front"), source_evidence(board)
    )

    assert entry.status == "COMPLETE"
    assert tuple(item.reference for item in entry.observations) == ("FID1",)


def test_back_side_and_exact_minimum_boundary_are_deterministic() -> None:
    (back_entry,) = pcb_fiducial_entries(requirement_map(minimum=1, side="back"), source_evidence())
    (front_entry,) = pcb_fiducial_entries(
        requirement_map(minimum=1, side="front"), source_evidence()
    )

    assert back_entry.status == "COMPLETE"
    assert tuple(item.reference for item in back_entry.observations) == ("FID2",)
    assert front_entry.status == "COMPLETE"
    assert tuple(item.reference for item in front_entry.observations) == ("FID1",)


def test_reordering_native_footprints_does_not_change_evidence() -> None:
    authored = requirement_map(side="either")
    native = source_evidence().snapshot
    first = pcb_fiducial_entries(authored, source_evidence(native))[0]
    reordered = native.model_copy(update={"footprints": tuple(reversed(native.footprints))})
    second = pcb_fiducial_entries(authored, source_evidence(reordered))[0]

    assert second == first


def test_report_contains_requirement_matches_source_identity_and_limitations() -> None:
    authored = requirement_map()
    observed = netlist(components={"U1": "Package_QFP:TQFP-48"})
    board = snapshot(
        (
            ("U1", "Package_QFP:TQFP-48", False, "F.Cu"),
            ("FID1", FIDUCIAL_FOOTPRINT, False, "F.Cu"),
            ("FID2", FIDUCIAL_FOOTPRINT, False, "B.Cu"),
            ("FID3", FIDUCIAL_FOOTPRINT, True, "F.Cu"),
            ("H1", "Synthetic:MountingHole", False, "F.Cu"),
        )
    )
    coverage = evaluate_pcb_fiducials(authored, "review", source_evidence(board), NETLIST_SHA256)
    inventory = complete_report(observed, board)
    report = evaluate(
        "synthetic-component-inventory",
        coach(observed).model_copy(update={"source_hashes": {BOARD_PATH: BOARD_SHA256}}),
        DesignLintPolicy(pcb_fiducial_map=authored),
        pcb_component_inventory_coverage=inventory.model_copy(
            update={"fiducial_coverage": coverage}
        ),
    )
    text = "\n".join(pcb_coverage_report_lines(report))

    assert report.status == "REVIEW"
    assert any(item.rule_id == RULE for item in report.findings)
    assert "PCB board fiducial coverage: INCOMPLETE" in text
    assert "board-fiducials: INCOMPLETE; 1 fitted match(es); 2 required on front" in text
    assert "FID1: Synthetic:Fiducial_1mm_Mask2mm" in text
    assert "does not verify panel fiducials" in text


def test_policy_can_promote_disable_or_exactly_ignore_the_review_candidate() -> None:
    authored = requirement_map()
    observed = netlist(components={"U1": "Package_QFP:TQFP-48"})
    board = snapshot(
        (
            ("U1", "Package_QFP:TQFP-48", False, "F.Cu"),
            ("FID1", FIDUCIAL_FOOTPRINT, False, "F.Cu"),
        )
    )
    coverage = evaluate_pcb_fiducials(authored, "review", source_evidence(board), NETLIST_SHA256)
    inventory = complete_report(observed, board).model_copy(update={"fiducial_coverage": coverage})
    source_coach = coach(observed).model_copy(
        update={"source_hashes": {BOARD_PATH: INVENTORY_BOARD_SHA256}}
    )
    review = evaluate(
        "synthetic-component-inventory",
        source_coach,
        DesignLintPolicy(pcb_fiducial_map=authored),
        pcb_component_inventory_coverage=inventory,
    )
    (finding,) = tuple(item for item in review.findings if item.rule_id == RULE)
    blocked = evaluate(
        "synthetic-component-inventory",
        source_coach,
        DesignLintPolicy(
            pcb_fiducial_map=authored,
            rules=(DesignLintRuleOverride(rule_id=RULE, mode="block", reason="handoff gate"),),
        ),
        pcb_component_inventory_coverage=inventory,
    )
    ignored = evaluate(
        "synthetic-component-inventory",
        source_coach,
        DesignLintPolicy(
            pcb_fiducial_map=authored,
            ignores=(
                DesignLintIgnore(rule_id=RULE, fingerprint=fingerprint(finding), reason="reviewed"),
            ),
        ),
        pcb_component_inventory_coverage=inventory,
    )
    off = evaluate(
        "synthetic-component-inventory",
        source_coach,
        DesignLintPolicy(
            pcb_fiducial_map=authored,
            rules=(DesignLintRuleOverride(rule_id=RULE, mode="off", reason="not required"),),
        ),
        pcb_component_inventory_coverage=inventory,
    )

    assert review.status == "REVIEW"
    assert blocked.status == "FAIL"
    assert ignored.status == "PASS"
    assert off.status == "PASS"
    assert not any(item.rule_id == RULE for item in off.findings)


def test_stale_map_board_or_netlist_evidence_blocks_instead_of_passing() -> None:
    authored = requirement_map()
    report = evaluate_pcb_fiducials(authored, "review", source_evidence(), NETLIST_SHA256)

    changed_map = normalize_pcb_fiducial_coverage(
        report,
        requirement_map(minimum=3),
        "review",
        source_hashes={BOARD_PATH: BOARD_SHA256},
        netlist_sha256=NETLIST_SHA256,
    )
    changed_board = normalize_pcb_fiducial_coverage(
        report,
        authored,
        "review",
        source_hashes={BOARD_PATH: "0" * 64},
        netlist_sha256=NETLIST_SHA256,
    )
    changed_netlist = normalize_pcb_fiducial_coverage(
        report,
        authored,
        "review",
        source_hashes={BOARD_PATH: BOARD_SHA256},
        netlist_sha256="0" * 64,
    )

    assert (changed_map.status, changed_board.status, changed_netlist.status) == (
        "BLOCKED",
        "BLOCKED",
        "BLOCKED",
    )
    assert all(item.issue for item in (changed_map, changed_board, changed_netlist))
    assert changed_map.issue != changed_board.issue != changed_netlist.issue


def test_missing_coverage_for_an_authored_map_is_blocked_not_clean() -> None:
    blocked = normalize_pcb_fiducial_coverage(
        PcbFiducialCoverageReport(),
        requirement_map(),
        "review",
        source_hashes={BOARD_PATH: BOARD_SHA256},
        netlist_sha256=NETLIST_SHA256,
    )

    assert blocked.status == "BLOCKED"
    assert blocked.issue is not None


def test_snapshot_schema_without_footprint_placements_is_blocked() -> None:
    old_snapshot = snapshot()
    legacy = PcbConnectivitySnapshot.model_validate(
        old_snapshot.model_dump(mode="python") | {"schema_version": "11"}
    )

    report = evaluate_pcb_fiducials(
        requirement_map(), "review", source_evidence(legacy), NETLIST_SHA256
    )

    assert report.status == "BLOCKED"
    assert report.snapshot_schema is None
    assert report.issue == (
        "Native PCB snapshot predates the schema 12 footprint placement inventory; "
        "fiducial count is unavailable"
    )
