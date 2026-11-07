"""Deterministic source-mapped differential-pair route-skew regressions."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from kicad_tooling.hwrepo.design_lint_pcb_requirement_candidates import (
    pcb_requirement_coverage_candidates,
)
from kicad_tooling.hwrepo.design_lint_pcb_route_skew_policy import (
    normalize_pcb_route_skew_policy,
)
from kicad_tooling.hwrepo.design_lint_pcb_route_skew_scan import (
    measure_route_skew_for_geometry_scan,
    route_measurement_enabled,
    route_measurement_mode,
    route_skew_enabled,
)
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.pcb_differential_pair_route_skew import (
    measure_differential_pair_route_skew,
)
from kicad_tooling.hwrepo.pcb_drc_models import PcbSignalPathRuleCoverageReport
from tests.design_lint_fixtures.pcb_differential_pair_route_skew import (
    geometry_evidence,
    route_map,
    route_snapshot,
    source_hashes,
    source_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]

RULE_ID = "pcb.differential_pair_route_skew"
LAYER_TRANSITION_RULE_ID = "pcb.differential_pair_route_layer_mismatch"
RouteSkewMode = Literal["review", "block", "off"]


def _measure(
    tmp_path: Path,
    *,
    maximum_skew_nm: int,
    positive_length_nm: int = 1_000_000,
    negative_length_nm: int,
    negative_branch: bool = False,
    negative_alternate_route: bool = False,
):
    snapshot = route_snapshot(
        positive_length_nm=positive_length_nm,
        negative_length_nm=negative_length_nm,
        negative_branch=negative_branch,
        negative_alternate_route=negative_alternate_route,
    )
    return measure_differential_pair_route_skew(
        route_map(maximum_skew_nm=maximum_skew_nm),
        source_netlist(),
        geometry_evidence(tmp_path, snapshot),
        source_hashes(),
        "d" * 64,
        "review",
    )


def test_excessive_routed_skew_is_reviewed_against_authored_bound(tmp_path: Path) -> None:
    report = _measure(tmp_path, maximum_skew_nm=500_000, negative_length_nm=2_000_000)

    assert report.status == "INCOMPLETE"
    entry = report.entries[0]
    assert entry.status == "EXCEEDS_LIMIT"
    assert entry.measured_skew_nm == 1_000_000
    parent = PcbSignalPathRuleCoverageReport(route_skew=report)
    candidates = pcb_requirement_coverage_candidates(pcb_signal_path_coverage=parent)
    finding = next(item for item in candidates if item.rule_id == RULE_ID)
    assert "1_000_000" in finding.message or "1000000" in finding.message
    assert finding.evidence["maximum_skew_nm"] == ("500000",)


def test_route_skew_at_authored_boundary_is_within_limit(tmp_path: Path) -> None:
    report = _measure(tmp_path, maximum_skew_nm=500_000, negative_length_nm=1_500_000)

    assert report.status == "COMPLETE"
    assert report.entries[0].status == "WITHIN_LIMIT"
    assert report.entries[0].measured_skew_nm == report.entries[0].max_skew_nm
    parent = PcbSignalPathRuleCoverageReport(route_skew=report)
    candidates = pcb_requirement_coverage_candidates(pcb_signal_path_coverage=parent)
    assert all(item.rule_id != RULE_ID for item in candidates)


def test_equal_routes_are_within_zero_skew_bound(tmp_path: Path) -> None:
    snapshot = route_snapshot(positive_length_nm=1_000_000, negative_length_nm=1_000_000)
    report = measure_differential_pair_route_skew(
        route_map(maximum_skew_nm=0),
        source_netlist(),
        geometry_evidence(tmp_path, snapshot),
        source_hashes(),
        "d" * 64,
        "review",
    )

    assert report.status == "COMPLETE"
    assert report.entries[0].measured_skew_nm == report.entries[0].max_skew_nm == 0


@pytest.mark.design_lint_rule(rule_id=LAYER_TRANSITION_RULE_ID)
def test_equal_length_pair_routes_with_different_layer_profiles_request_review(
    tmp_path: Path,
) -> None:
    report = measure_differential_pair_route_skew(
        route_map(maximum_skew_nm=0),
        source_netlist(),
        geometry_evidence(
            tmp_path,
            route_snapshot(
                positive_length_nm=1_000_000,
                negative_length_nm=1_000_000,
                negative_layer_transition=True,
            ),
        ),
        source_hashes(),
        "d" * 64,
        "review",
    )

    assert report.status == "COMPLETE"
    assert report.entries[0].measured_skew_nm == 0
    candidates = pcb_requirement_coverage_candidates(
        pcb_signal_path_coverage=PcbSignalPathRuleCoverageReport(route_skew=report)
    )
    findings = [item for item in candidates if item.rule_id == LAYER_TRANSITION_RULE_ID]
    assert len(findings) == 1
    assert findings[0].evidence["route_layer_profiles"] == (
        "negative-path: USB_DN J1.2 to U1.2; F.Cu -> B.Cu",
        "positive-path: USB_DP J1.1 to U1.1; F.Cu",
    )
    assert "does not establish a signal-integrity defect" in findings[0].message


@pytest.mark.design_lint_rule(rule_id=LAYER_TRANSITION_RULE_ID)
def test_equal_pair_layer_profiles_are_quiet(tmp_path: Path) -> None:
    report = _measure(
        tmp_path,
        maximum_skew_nm=0,
        positive_length_nm=1_000_000,
        negative_length_nm=1_000_000,
    )

    candidates = pcb_requirement_coverage_candidates(
        pcb_signal_path_coverage=PcbSignalPathRuleCoverageReport(route_skew=report)
    )
    assert all(item.rule_id != LAYER_TRANSITION_RULE_ID for item in candidates)


@pytest.mark.design_lint_rule(rule_id=LAYER_TRANSITION_RULE_ID)
def test_pair_layer_profile_evidence_is_stable_when_native_items_are_reordered(
    tmp_path: Path,
) -> None:
    requirements = route_map(maximum_skew_nm=0)
    snapshot = route_snapshot(
        positive_length_nm=1_000_000,
        negative_length_nm=1_000_000,
        negative_layer_transition=True,
    )
    reordered = snapshot.model_copy(
        update={"pads": tuple(reversed(snapshot.pads)), "tracks": tuple(reversed(snapshot.tracks))}
    )
    reports = tuple(
        measure_differential_pair_route_skew(
            requirements,
            source_netlist(),
            geometry_evidence(tmp_path, current),
            source_hashes(),
            "d" * 64,
            "review",
        )
        for current in (snapshot, reordered)
    )

    findings = tuple(
        next(
            item
            for item in pcb_requirement_coverage_candidates(
                pcb_signal_path_coverage=PcbSignalPathRuleCoverageReport(route_skew=report)
            )
            if item.rule_id == LAYER_TRANSITION_RULE_ID
        )
        for report in reports
    )
    assert findings[0].evidence == findings[1].evidence


def test_route_lengths_remain_deterministic_when_maps_and_tracks_are_reordered(
    tmp_path: Path,
) -> None:
    requirements = route_map(maximum_skew_nm=500_000)
    original_snapshot = route_snapshot()
    reordered_snapshot = original_snapshot.model_copy(
        update={
            "pads": tuple(reversed(original_snapshot.pads)),
            "tracks": tuple(reversed(original_snapshot.tracks)),
        }
    )
    reordered_map = type(requirements).model_validate(
        requirements.model_dump() | {"paths": tuple(reversed(requirements.paths))}
    )
    original = measure_differential_pair_route_skew(
        requirements,
        source_netlist(),
        geometry_evidence(tmp_path, original_snapshot),
        source_hashes(),
        "d" * 64,
        "review",
    )
    reordered = measure_differential_pair_route_skew(
        reordered_map,
        source_netlist(),
        geometry_evidence(tmp_path, reordered_snapshot),
        source_hashes(),
        "d" * 64,
        "review",
    )

    assert original.entries == reordered.entries
    assert original.entries[0].measured_skew_nm == 1_000_000


def test_route_measurement_rejects_endpoints_missing_from_source_netlist(tmp_path: Path) -> None:
    snapshot = route_snapshot()
    netlist = source_netlist().model_copy(update={"nets": {"USB_DP": ("J1.1", "U1.1")}})
    report = measure_differential_pair_route_skew(
        route_map(),
        netlist,
        geometry_evidence(tmp_path, snapshot),
        source_hashes(),
        "d" * 64,
        "review",
    )

    assert report.status == "INCOMPLETE"
    assert report.entries[0].status == "INCOMPLETE"
    issue = report.entries[0].paths[0].issue
    assert issue is not None and "USB_DN" in issue


def test_missing_member_route_is_incomplete_not_clean(tmp_path: Path) -> None:
    snapshot = route_snapshot(missing_nets=("USB_DN",))
    report = measure_differential_pair_route_skew(
        route_map(),
        source_netlist(),
        geometry_evidence(tmp_path, snapshot),
        source_hashes(),
        "d" * 64,
        "review",
    )

    assert report.status == "INCOMPLETE"
    assert report.entries[0].status == "INCOMPLETE"
    issue = report.entries[0].paths[0].issue
    assert issue is not None and "No native track is observed" in issue


def test_unique_mapped_route_resolves_with_an_off_path_branch(tmp_path: Path) -> None:
    report = _measure(
        tmp_path,
        maximum_skew_nm=500_000,
        negative_length_nm=1_500_000,
        negative_branch=True,
    )

    assert report.status == "COMPLETE"
    assert report.entries[0].status == "WITHIN_LIMIT"
    assert report.entries[0].measured_skew_nm == 500_000
    assert report.entries[0].paths[0].status == "RESOLVED"
    assert report.entries[0].paths[0].length_nm == 1_500_000


def test_alternate_route_between_mapped_pads_stays_incomplete(tmp_path: Path) -> None:
    report = _measure(
        tmp_path,
        maximum_skew_nm=500_000,
        negative_length_nm=2_000_000,
        negative_alternate_route=True,
    )

    assert report.status == "INCOMPLETE"
    assert report.entries[0].status == "INCOMPLETE"
    route = report.entries[0].paths[0]
    assert route.status == "INCOMPLETE"
    assert route.issue is not None and "More than one native track chain" in route.issue


def test_route_skew_can_be_disabled_by_the_project_rule_override(tmp_path: Path) -> None:
    report = measure_differential_pair_route_skew(
        route_map(),
        source_netlist(),
        geometry_evidence(tmp_path, route_snapshot()),
        source_hashes(),
        "d" * 64,
        "off",
    )

    assert report.status == "DISABLED"
    assert report.mode == "off"
    assert not pcb_requirement_coverage_candidates(
        pcb_signal_path_coverage=PcbSignalPathRuleCoverageReport(route_skew=report)
    )


def test_active_route_skew_requires_current_source_inventory(tmp_path: Path) -> None:
    report = _measure(tmp_path, maximum_skew_nm=500_000, negative_length_nm=2_000_000)
    changed_sources = source_hashes() | {"projects/synthetic/board.kicad_pcb": "9" * 64}

    normalized = normalize_pcb_route_skew_policy(
        report,
        requirements=route_map(),
        mode="block",
        source_hashes=changed_sources,
    )

    assert normalized.status == "BLOCKED"
    assert normalized.mode == "block"
    assert normalized.issue is not None and "source inventory" in normalized.issue


def test_absent_pair_bundle_is_not_requested(tmp_path: Path) -> None:
    requirements = route_map().model_copy(update={"bundles": ()})
    report = measure_differential_pair_route_skew(
        requirements,
        source_netlist(),
        geometry_evidence(tmp_path, route_snapshot()),
        source_hashes(),
        "d" * 64,
        "review",
    )

    assert report.status == "NOT_REQUESTED"
    assert report.entries == ()


@pytest.mark.parametrize("mode", ("review", "block", "off"))
def test_scan_uses_the_project_route_skew_override(tmp_path: Path, mode: RouteSkewMode) -> None:
    requirements = route_map()
    policy = DesignLintPolicy(
        pcb_signal_path_rule_map=requirements,
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Synthetic project route-skew disposition",
            ),
        ),
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-route-skew",
        netlist_sha256="d" * 64,
        observed=source_netlist(),
        source_hashes=source_hashes(),
    )
    snapshot = (
        route_snapshot(
            positive_length_nm=1_000_000,
            negative_length_nm=1_000_000,
            negative_layer_transition=True,
        )
        if mode == "off"
        else route_snapshot()
    )
    signal_path_report = measure_route_skew_for_geometry_scan(
        PcbSignalPathRuleCoverageReport(),
        policy=policy,
        coach=coach,
        evidence=geometry_evidence(tmp_path, snapshot),
        netlist_sha256="d" * 64,
    )

    assert route_skew_enabled(policy) is (mode != "off")
    assert route_measurement_enabled(policy)
    if mode == "off":
        assert route_measurement_mode(policy) == "review"
        assert signal_path_report.route_skew is not None
        layer_candidate = next(
            item
            for item in pcb_requirement_coverage_candidates(
                pcb_signal_path_coverage=signal_path_report
            )
            if item.rule_id == LAYER_TRANSITION_RULE_ID
        )
        assert layer_candidate.evidence["route_layer_profiles"]
    else:
        assert route_measurement_mode(policy) == mode
        assert signal_path_report.route_skew is not None
        assert signal_path_report.route_skew.mode == mode
        assert signal_path_report.route_skew.entries[0].status == "EXCEEDS_LIMIT"


def test_both_pair_route_rules_can_be_disabled_without_capturing_route_evidence() -> None:
    policy = DesignLintPolicy(
        pcb_signal_path_rule_map=route_map(),
        rules=tuple(
            DesignLintRuleOverride(
                rule_id=rule_id,
                mode="off",
                reason="Synthetic project rule suppression",
            )
            for rule_id in (RULE_ID, LAYER_TRANSITION_RULE_ID)
        ),
    )

    assert not route_measurement_enabled(policy)
    assert route_measurement_mode(policy) == "off"
