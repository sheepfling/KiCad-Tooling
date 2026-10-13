"""Configured touch-pad-to-filled-copper clearance lint behavior."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint_pcb_coverage_common import map_sha256
from kicad_tooling.hwrepo.pcb_touch_pad_clearance import (
    touch_pad_clearance_entries,
    touch_pad_clearance_violations,
)
from kicad_tooling.hwrepo.pcb_touch_pad_clearance_models import (
    PcbTouchPadClearanceCoverageReport,
    PcbTouchPadClearanceMap,
    PcbTouchPadClearanceRequirement,
)
from tests.pcb_touch_pad_clearance_support import (
    clearance_map,
    coverage_report,
    netlist,
    requirement,
    snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_below_project_minimum_emits_source_bound_review_candidate() -> None:
    authored = clearance_map(minimum_clearance_nm=800_000)
    entries = touch_pad_clearance_entries(
        authored,
        snapshot(distance_nm=500_000, minimum_clearance_nm=800_000),
        netlist(),
    )
    (entry,) = entries
    report = coverage_report(authored=authored, entry=entry)

    (candidate,) = touch_pad_clearance_violations(report)

    assert entry.status == "COMPLETE"
    assert entry.schematic_pad_net == entry.expected_pad_net == "SIGNAL"
    assert entry.observed_pad_net == "SIGNAL"
    assert entry.measured_clearance_nm == 500_000
    assert entry.violates_minimum_clearance
    assert report.map_sha256 == map_sha256(authored)
    assert candidate.rule_id == "pcb.touch_pad_reference_clearance"
    assert candidate.evidence["minimum_clearance_nm"] == ("800000",)
    assert candidate.evidence["measured_clearance_nm"] == ("500000",)


def test_measurement_at_the_project_minimum_is_a_valid_control() -> None:
    authored = clearance_map(minimum_clearance_nm=500_000)
    (entry,) = touch_pad_clearance_entries(authored, snapshot(), netlist())
    report = coverage_report(authored=authored, entry=entry)

    assert entry.status == "COMPLETE"
    assert not entry.violates_minimum_clearance
    assert touch_pad_clearance_violations(report) == ()


def test_raising_project_minimum_alone_changes_candidate() -> None:
    valid_map = clearance_map(minimum_clearance_nm=400_000)
    strict_map = clearance_map(minimum_clearance_nm=600_000)
    (valid_entry,) = touch_pad_clearance_entries(
        valid_map,
        snapshot(distance_nm=500_000, minimum_clearance_nm=400_000),
        netlist(),
    )
    (strict_entry,) = touch_pad_clearance_entries(
        strict_map,
        snapshot(distance_nm=500_000, minimum_clearance_nm=600_000),
        netlist(),
    )

    assert valid_entry.measured_clearance_nm == strict_entry.measured_clearance_nm == 500_000
    assert not valid_entry.violates_minimum_clearance
    assert strict_entry.violates_minimum_clearance


def test_schematic_net_divergence_keeps_a_geometric_measurement_incomplete() -> None:
    authored = clearance_map()
    (entry,) = touch_pad_clearance_entries(
        authored,
        snapshot(),
        netlist(pad_net="OTHER"),
    )

    assert entry.status == "INCOMPLETE"
    assert entry.schematic_pad_net == "OTHER"
    assert entry.observed_pad_net == "SIGNAL"
    assert any("schematic netlist" in issue for issue in entry.issues)
    assert touch_pad_clearance_violations(coverage_report(authored=authored, entry=entry))


def test_board_pad_net_divergence_is_not_mistaken_for_valid_clearance() -> None:
    authored = clearance_map()
    (entry,) = touch_pad_clearance_entries(
        authored,
        snapshot(board_pad_net="BOARD_ONLY"),
        netlist(),
    )

    assert entry.status == "INCOMPLETE"
    assert entry.schematic_pad_net == "SIGNAL"
    assert entry.observed_pad_net == "BOARD_ONLY"
    assert any("native touch-pad net" in issue for issue in entry.issues)


def test_missing_filled_reference_copper_is_an_incomplete_evidence_candidate() -> None:
    authored = clearance_map()
    (entry,) = touch_pad_clearance_entries(
        authored,
        snapshot(status="NO_FILLED_REFERENCE_COPPER"),
        netlist(),
    )

    assert entry.status == "INCOMPLETE"
    assert entry.measured_clearance_nm is None
    assert any("NO_FILLED_REFERENCE_COPPER" in issue for issue in entry.issues)


def test_touch_clearance_maps_require_positive_exact_and_unique_requirements() -> None:
    with pytest.raises(ValidationError, match="greater than 0"):
        requirement(minimum_clearance_nm=0)

    repeated_pad = PcbTouchPadClearanceRequirement(
        id="second-requirement",
        pad="J1.1",
        expected_pad_net="SIGNAL",
        reference_net="GND",
        layer="F.Cu",
        minimum_clearance_nm=200_000,
    )
    with pytest.raises(ValidationError, match="pad/layer/reference-net tuples"):
        PcbTouchPadClearanceMap(
            basis="Synthetic duplicate exact-pad scope",
            requirements=(requirement(), repeated_pad),
        )


def test_source_bound_report_must_cover_each_mapped_requirement_once() -> None:
    authored = clearance_map()
    (entry,) = touch_pad_clearance_entries(authored, snapshot(), netlist())
    report = coverage_report(authored=authored, entry=entry)
    invalid = report.model_dump()
    invalid["requirement_count"] = 2

    with pytest.raises(ValidationError, match="every mapped requirement"):
        PcbTouchPadClearanceCoverageReport.model_validate(invalid)
