"""Typed source regressions for schematic text placement and wire overlap."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint_schematic_geometry import schematic_geometry_candidates
from kicad_tooling.hwrepo.design_lint_schematic_text_candidate_evidence import (
    CoincidentTextAnchorsSource,
    FreeTextOverlapSource,
    FreeTextWireOverlapSource,
    SchematicTextGeometryCandidate,
)
from kicad_tooling.hwrepo.schematic_geometry import (
    SchematicGeometryScan,
    scan_wire_ends_on_pin_lines,
)
from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    free_text_anchor_fixture,
    free_text_objects_fixture,
    free_text_wire_fixture,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.schematic_text_lint,
    pytest.mark.evidence_lint,
]


def _scan(source: bytes, source_name: str) -> SchematicGeometryScan:
    return scan_wire_ends_on_pin_lines(
        source,
        source_path=f"synthetic/{source_name}.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )


def _candidate_for(scan: SchematicGeometryScan, rule_id: str) -> SchematicTextGeometryCandidate:
    candidate = next(
        item for item in schematic_geometry_candidates(scan) if item.rule_id == rule_id
    )
    assert isinstance(candidate, SchematicTextGeometryCandidate)
    return candidate


def test_coincident_text_candidate_retains_both_anchors() -> None:
    scan = _scan(free_text_anchor_fixture((25.4, 25.4), (25.4, 25.4)), "coincident-text")
    candidate = _candidate_for(scan, "schematic.coincident_text_anchors")

    assert isinstance(candidate.source_evidence, CoincidentTextAnchorsSource)
    assert candidate.source_evidence.scan is scan
    assert candidate.source_evidence.finding is scan.coincident_text_anchors[0]
    assert candidate.evidence["anchor_mm"] == ("25.400000,25.400000",)
    assert candidate.evidence["first_text_uuid"] == ("d0000000-0000-4000-8000-000000000001",)
    assert candidate.evidence["second_text_uuid"] == ("d0000000-0000-4000-8000-000000000002",)


def test_free_text_overlap_candidate_retains_both_measured_envelopes() -> None:
    scan = _scan(
        free_text_objects_fixture(
            "LONG_LABEL_ALPHA", (25.4, 25.4), "LONG_LABEL_BETA", (29.0, 25.4)
        ),
        "text-overlap",
    )
    candidate = _candidate_for(scan, "schematic.free_text_overlap")

    assert isinstance(candidate.source_evidence, FreeTextOverlapSource)
    assert candidate.source_evidence.scan is scan
    assert candidate.source_evidence.finding is scan.free_text_overlaps[0]
    assert candidate.evidence["first_text_box_mm"] == (
        ",".join(f"{value:.6f}" for value in scan.free_text_overlaps[0].first_box_mm),
    )
    assert candidate.evidence["overlap_box_mm"] == (
        ",".join(f"{value:.6f}" for value in scan.free_text_overlaps[0].overlap_box_mm),
    )


def test_free_text_wire_candidate_retains_the_overlap_segment() -> None:
    scan = _scan(free_text_wire_fixture("WIRE CROSSING FAULT", (88.9, 71.12)), "text-wire")
    candidate = _candidate_for(scan, "schematic.free_text_over_wire")

    assert isinstance(candidate.source_evidence, FreeTextWireOverlapSource)
    assert candidate.source_evidence.scan is scan
    assert candidate.source_evidence.finding is scan.free_text_wire_overlaps[0]
    assert candidate.evidence["overlap_segment_mm"] == (
        ",".join(
            f"{value:.6f}"
            for value in (
                *scan.free_text_wire_overlaps[0].wire_segment_start_mm,
                *scan.free_text_wire_overlaps[0].wire_segment_end_mm,
            )
        ),
    )
    assert candidate.evidence["overlap_length_mm"] == (
        f"{scan.free_text_wire_overlaps[0].overlap_length_mm:.6f}",
    )


def test_text_candidate_rejects_projection_drift_and_detached_source() -> None:
    scan = _scan(free_text_anchor_fixture((25.4, 25.4), (25.4, 25.4)), "coincident-text")
    candidate = _candidate_for(scan, "schematic.coincident_text_anchors")

    with pytest.raises(ValueError, match="match their typed source projection"):
        replace(candidate, evidence={**candidate.evidence, "anchor_mm": ("stale",)})
    with pytest.raises(ValueError, match="observation from its source scan"):
        CoincidentTextAnchorsSource(
            replace(scan, coincident_text_anchors=()), scan.coincident_text_anchors[0]
        )
