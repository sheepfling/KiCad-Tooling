"""Typed source regressions for schematic label attachment hints."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_schematic_geometry import schematic_geometry_candidates
from kicad_tooling.hwrepo.design_lint_schematic_geometry_candidate_evidence import (
    LabelNearWireEndpointSource,
    SchematicLabelEndpointCandidate,
)
from kicad_tooling.hwrepo.schematic_geometry import scan_wire_ends_on_pin_lines

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
]


def test_label_endpoint_candidate_retains_label_and_nearby_wire_records() -> None:
    path = Path(__file__).parent / "fixtures/design_lint/label-near-wire-endpoint.kicad_sch"
    scan = scan_wire_ends_on_pin_lines(
        path.read_bytes(),
        source_path="tests/fixtures/design_lint/label-near-wire-endpoint.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )

    candidate = next(
        item
        for item in schematic_geometry_candidates(scan)
        if item.rule_id == "schematic.label_near_wire_endpoint"
    )

    assert isinstance(candidate, SchematicLabelEndpointCandidate)
    assert isinstance(candidate.source_evidence, LabelNearWireEndpointSource)
    assert candidate.source_evidence.scan is scan
    assert candidate.source_evidence.finding is scan.labels_near_wire_endpoints[0]
    assert candidate.evidence["label_uuid"] == (scan.labels_near_wire_endpoints[0].label_uuid,)
    assert candidate.evidence["near_wire_endpoints"] == (
        "b0000000-0000-4000-8000-000000000005@101.600000,71.120000 (0.500000 mm)",
    )
    assert candidate.evidence["schematic_sha256"] == (scan.source_sha256,)


def test_label_endpoint_candidate_rejects_projection_drift_and_detached_scan() -> None:
    path = Path(__file__).parent / "fixtures/design_lint/label-near-wire-endpoint.kicad_sch"
    scan = scan_wire_ends_on_pin_lines(
        path.read_bytes(),
        source_path="tests/fixtures/design_lint/label-near-wire-endpoint.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    candidate = next(
        item
        for item in schematic_geometry_candidates(scan)
        if item.rule_id == "schematic.label_near_wire_endpoint"
    )

    with pytest.raises(ValueError, match="match their typed source projection"):
        replace(candidate, evidence={**candidate.evidence, "label_uuid": ("stale-label",)})
    with pytest.raises(ValueError, match="observation from its source scan"):
        LabelNearWireEndpointSource(
            replace(scan, labels_near_wire_endpoints=()), scan.labels_near_wire_endpoints[0]
        )
