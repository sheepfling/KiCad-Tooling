"""Typed source regressions for schematic symbol-body obstruction candidates."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint_schematic_geometry import schematic_geometry_candidates
from kicad_tooling.hwrepo.design_lint_schematic_symbol_body_candidate_evidence import (
    FreeTextSymbolBodyOverlapSource,
    SchematicSymbolBodyObstructionCandidate,
    WireThroughSymbolBodySource,
)
from kicad_tooling.hwrepo.schematic_geometry import (
    SchematicGeometryScan,
    scan_wire_ends_on_pin_lines,
)
from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    free_text_symbol_body_fixture,
    symbol_body_wire_fixture,
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


def _candidate_for(
    scan: SchematicGeometryScan, rule_id: str
) -> SchematicSymbolBodyObstructionCandidate:
    candidate = next(
        item for item in schematic_geometry_candidates(scan) if item.rule_id == rule_id
    )
    assert isinstance(candidate, SchematicSymbolBodyObstructionCandidate)
    return candidate


def test_free_text_body_candidate_retains_text_and_symbol_envelopes() -> None:
    scan = _scan(free_text_symbol_body_fixture(), "text-body")
    candidate = _candidate_for(scan, "schematic.free_text_over_symbol_body")

    assert isinstance(candidate.source_evidence, FreeTextSymbolBodyOverlapSource)
    assert candidate.source_evidence.scan is scan
    assert candidate.source_evidence.finding is scan.free_text_symbol_body_overlaps[0]
    assert candidate.evidence["text_uuid"] == ("f2000000-0000-4000-8000-000000000001",)
    assert candidate.evidence["body_box_mm"] == ("74.930000,73.660000,77.470000,78.740000",)
    assert candidate.evidence["overlap_box_mm"] == (
        ",".join(f"{value:.6f}" for value in scan.free_text_symbol_body_overlaps[0].overlap_box_mm),
    )


def test_wire_body_candidate_retains_segment_and_optional_pin_matches() -> None:
    scan = _scan(symbol_body_wire_fixture(), "wire-body")
    candidate = _candidate_for(scan, "schematic.wire_through_symbol_body")

    assert isinstance(candidate.source_evidence, WireThroughSymbolBodySource)
    assert candidate.source_evidence.scan is scan
    assert candidate.source_evidence.finding is scan.wires_through_symbol_bodies[0]
    assert candidate.evidence["overlap_segment_mm"] == ("75.130000,76.200000,77.270000,76.200000",)
    assert candidate.evidence["pin_endpoint_numbers"] == ()
    assert candidate.evidence["pin_endpoint_names"] == ()
    assert candidate.evidence["pin_endpoint_mm"] == ()


def test_symbol_body_candidate_rejects_projection_drift_and_detached_source() -> None:
    scan = _scan(free_text_symbol_body_fixture(), "text-body")
    candidate = _candidate_for(scan, "schematic.free_text_over_symbol_body")

    with pytest.raises(ValueError, match="match their typed source projection"):
        replace(candidate, evidence={**candidate.evidence, "text_uuid": ("stale-text",)})
    with pytest.raises(ValueError, match="observation from its source scan"):
        FreeTextSymbolBodyOverlapSource(
            replace(scan, free_text_symbol_body_overlaps=()),
            scan.free_text_symbol_body_overlaps[0],
        )
