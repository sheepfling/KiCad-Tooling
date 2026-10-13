"""Synthetic regressions for opt-in board-only footprint review."""

from __future__ import annotations

import hashlib
from typing import Literal

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_board_only_candidates import (
    pcb_board_only_footprint_candidates,
)
from kicad_tooling.hwrepo.design_lint_pcb_report import pcb_coverage_report_lines
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    PcbConnectivitySnapshot,
)
from kicad_tooling.hwrepo.pcb_board_only_footprints import board_only_pcb_footprints
from kicad_tooling.hwrepo.pcb_component_inventory import (
    evaluate_native_component_inventory_coverage,
)
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
)
from tests.design_lint_fixtures.pcb_component_inventory import (
    BOARD_SHA256,
    NETLIST_SHA256,
    PROBE_SHA256,
    SNAPSHOT_SHA256,
    coach,
    netlist,
    snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]
RULE = "pcb.board_only_footprint"


def _coverage(
    observed: NetlistContract,
    board: PcbConnectivitySnapshot,
    *,
    mode: Literal["review", "block", "off"] = "review",
) -> PcbComponentInventoryCoverageReport:
    return evaluate_native_component_inventory_coverage(
        observed,
        board,
        mode="off",
        netlist_sha256=NETLIST_SHA256,
        board_path="synthetic/controller.kicad_pcb",
        board_sha256=BOARD_SHA256,
        snapshot_path="build/design-lint/native/snapshot.json",
        snapshot_sha256=SNAPSHOT_SHA256,
        probe_sha256=PROBE_SHA256,
        board_only_mode=mode,
    )


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_extra_board_reference_is_reported_without_classifying_its_intent() -> None:
    observed = netlist(components={"J1": "Connector:USB_B", "U1": "Package_SO:SOIC-8"})
    board = snapshot(
        "J1",
        "U1",
        "J2",
        "H_MOUNT1",
        footprint_by_reference={"J2": "Connector:DB9", "H_MOUNT1": "MountingHole:NPTH"},
    )

    findings = board_only_pcb_footprints(observed, board)
    assert tuple((item.reference, item.footprint) for item in findings) == (
        ("H_MOUNT1", "MountingHole:NPTH"),
        ("J2", "Connector:DB9"),
    )

    coverage = _coverage(observed, board)
    candidates = pcb_board_only_footprint_candidates(coverage)
    assert tuple(item.subject for item in candidates) == (
        "H_MOUNT1: PCB footprint has no schematic counterpart",
        "J2: PCB footprint has no schematic counterpart",
    )
    assert candidates[1].evidence["footprint"] == ("Connector:DB9",)
    assert candidates[1].evidence["board_sha256"] == (BOARD_SHA256,)
    assert "may be an intentional" in candidates[1].message

    report = evaluate(
        "synthetic-board-only-footprints",
        coach(observed),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(rule_id=RULE, mode="review", reason="inspect board extras"),
            )
        ),
        pcb_component_inventory_coverage=coverage,
    )
    rendered = pcb_coverage_report_lines(report)
    assert "PCB board-only footprint review: COMPLETE (mode: review)" in rendered
    assert "  No schematic counterpart: J2 (Connector:DB9)" in rendered


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_board_only_review_is_opt_in_and_supports_policy_and_exact_ignore() -> None:
    observed = netlist(components={"J1": "Connector:USB_B"})
    coverage = _coverage(observed, snapshot("J1", "H_MOUNT1"))
    (candidate,) = pcb_board_only_footprint_candidates(coverage)

    default = evaluate(
        "synthetic-board-only-footprints",
        coach(observed),
        DesignLintPolicy(),
        pcb_component_inventory_coverage=coverage,
    )
    (default_finding,) = tuple(item for item in default.findings if item.rule_id == RULE)
    assert default_finding.disposition == "RULE_OFF"

    review_policy = DesignLintPolicy(
        rules=(DesignLintRuleOverride(rule_id=RULE, mode="review", reason="review extras"),)
    )
    reviewed = evaluate(
        "synthetic-board-only-footprints",
        coach(observed),
        review_policy,
        pcb_component_inventory_coverage=coverage,
    )
    (review_finding,) = tuple(item for item in reviewed.findings if item.rule_id == RULE)
    assert review_finding.mode == "review"
    assert review_finding.disposition == "OPEN"

    blocked = evaluate(
        "synthetic-board-only-footprints",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE, mode="block", reason="approved board"),)
        ),
        pcb_component_inventory_coverage=coverage,
    )
    (block_finding,) = tuple(item for item in blocked.findings if item.rule_id == RULE)
    assert block_finding.mode == "block"
    assert block_finding.disposition == "OPEN"

    ignored_policy = review_policy.model_copy(
        update={
            "ignores": (
                DesignLintIgnore(
                    rule_id=RULE,
                    fingerprint=fingerprint(candidate),
                    reason="intentional board-only mounting hole",
                ),
            )
        }
    )
    ignored = evaluate(
        "synthetic-board-only-footprints",
        coach(observed),
        ignored_policy,
        pcb_component_inventory_coverage=coverage,
    )
    (ignored_finding,) = tuple(item for item in ignored.findings if item.rule_id == RULE)
    assert ignored_finding.disposition == "IGNORED"

    changed = coverage.model_copy(
        update={"snapshot_sha256": hashlib.sha256(b"new native board snapshot").hexdigest()}
    )
    stale = evaluate(
        "synthetic-board-only-footprints",
        coach(observed),
        ignored_policy,
        pcb_component_inventory_coverage=changed,
    )
    (stale_finding,) = tuple(item for item in stale.findings if item.rule_id == RULE)
    assert stale_finding.disposition == "OPEN"
    assert tuple(item.rule_id for item in stale.stale_ignores) == (RULE,)


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_schematic_reference_case_and_input_order_do_not_change_results() -> None:
    first = board_only_pcb_footprints(
        netlist(components={"J1": "Connector:USB_B", "U1": "Package_SO:SOIC-8"}),
        snapshot("j1", "EXTRA2", "extra1"),
    )
    reordered = board_only_pcb_footprints(
        netlist(components={"U1": "Package_SO:SOIC-8", "j1": "Connector:USB_B"}),
        snapshot("extra1", "EXTRA2", "J1"),
    )

    assert first == reordered
    assert tuple(item.reference for item in first) == ("extra1", "EXTRA2")


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_missing_or_unsupported_native_evidence_blocks_board_only_coverage() -> None:
    observed = netlist(components={"J1": "Connector:USB_B"})
    unavailable = evaluate_native_component_inventory_coverage(
        None,
        snapshot("J2"),
        mode="off",
        netlist_sha256=None,
        board_path="synthetic/controller.kicad_pcb",
        board_sha256=BOARD_SHA256,
        snapshot_path="build/design-lint/native/snapshot.json",
        snapshot_sha256=SNAPSHOT_SHA256,
        probe_sha256=PROBE_SHA256,
        board_only_mode="review",
    )
    (blocked_candidate,) = pcb_board_only_footprint_candidates(unavailable)
    assert unavailable.status == "BLOCKED"
    assert blocked_candidate.rule_id == RULE
    assert "No conclusion" in blocked_candidate.message

    unsupported = _coverage(observed, snapshot("J2", schema_version="11"))
    assert unsupported.status == "BLOCKED"
    assert unsupported.board_only_footprint_coverage.status == "BLOCKED"
    assert pcb_board_only_footprint_candidates(unsupported)


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_snapshot_and_netlist_duplicate_references_fail_closed() -> None:
    with pytest.raises(ValueError, match="duplicate case-insensitive"):
        board_only_pcb_footprints(
            netlist(components={"J1": "Connector:USB_B", "j1": "Connector:USB_B"}),
            snapshot("J1"),
        )

    with pytest.raises(ValueError, match="duplicate footprint references"):
        board_only_pcb_footprints(
            netlist(components={"J1": "Connector:USB_B"}),
            snapshot("J1", "j1"),
        )


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_matching_board_references_are_a_quiet_control() -> None:
    observed = netlist(components={"J1": "Connector:USB_B", "U1": "Package_SO:SOIC-8"})
    coverage = _coverage(observed, snapshot("J1", "U1"))

    assert coverage.board_only_footprint_coverage.footprints == ()
    assert pcb_board_only_footprint_candidates(coverage) == ()
