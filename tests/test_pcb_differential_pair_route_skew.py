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
RouteSkewMode = Literal["review", "block", "off"]


def _measure(tmp_path: Path, *, maximum_skew_nm: int, negative_length_nm: int):
    snapshot = route_snapshot(negative_length_nm=negative_length_nm)
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
    signal_path_report = measure_route_skew_for_geometry_scan(
        PcbSignalPathRuleCoverageReport(),
        policy=policy,
        coach=coach,
        evidence=geometry_evidence(tmp_path, route_snapshot()),
        netlist_sha256="d" * 64,
    )

    assert route_skew_enabled(policy) is (mode != "off")
    if mode == "off":
        assert signal_path_report.route_skew is None
    else:
        assert signal_path_report.route_skew is not None
        assert signal_path_report.route_skew.mode == mode
        assert signal_path_report.route_skew.entries[0].status == "EXCEEDS_LIMIT"
