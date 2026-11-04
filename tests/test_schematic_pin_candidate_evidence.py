"""Typed source regressions for pin and wire geometry candidates."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_schematic_geometry import schematic_geometry_candidates
from kicad_tooling.hwrepo.design_lint_schematic_geometry_candidate_evidence import (
    PinTipOnWireInteriorSource,
    SchematicPinGeometryCandidate,
    WireEndOnPinLineSource,
    WireEndpointNearPinTipSource,
)
from kicad_tooling.hwrepo.schematic_geometry import scan_wire_ends_on_pin_lines

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
]

_FIXTURES = Path(__file__).parent / "fixtures/design_lint"


@pytest.mark.parametrize(
    ("filename", "rule_id", "source_type", "scan_attribute"),
    (
        (
            "near-miss-pin-line.kicad_sch",
            "schematic.wire_end_on_pin_line",
            WireEndOnPinLineSource,
            "findings",
        ),
        (
            "pin-on-wire-middle-no-junction.kicad_sch",
            "schematic.pin_tip_on_wire_interior",
            PinTipOnWireInteriorSource,
            "pin_tip_on_wire_interiors",
        ),
        (
            "wire-end-near-pin-tip.kicad_sch",
            "schematic.wire_endpoint_near_pin_tip",
            WireEndpointNearPinTipSource,
            "wire_endpoints_near_pin_tips",
        ),
    ),
)
def test_pin_geometry_candidate_retains_its_exact_scan_observation(
    filename: str,
    rule_id: str,
    source_type: type[
        WireEndOnPinLineSource | PinTipOnWireInteriorSource | WireEndpointNearPinTipSource
    ],
    scan_attribute: str,
) -> None:
    path = _FIXTURES / filename
    source_path = f"tests/fixtures/design_lint/{filename}"
    scan = scan_wire_ends_on_pin_lines(
        path.read_bytes(),
        source_path=source_path,
        kicad_version="10.0.6",
        unconnected_pins=frozenset({"R1.1"}),
    )

    candidate = next(
        item for item in schematic_geometry_candidates(scan) if item.rule_id == rule_id
    )

    assert isinstance(candidate, SchematicPinGeometryCandidate)
    assert isinstance(candidate.source_evidence, source_type)
    assert candidate.source_evidence.scan is scan
    assert candidate.source_evidence.finding is getattr(scan, scan_attribute)[0]
    assert candidate.evidence["schematic_sha256"] == (scan.source_sha256,)
    assert candidate.evidence["sheet_instance_path"] == (
        candidate.source_evidence.finding.sheet_instance_path,
    )


def test_pin_geometry_candidate_rejects_projection_drift_and_detached_scan() -> None:
    path = _FIXTURES / "near-miss-pin-line.kicad_sch"
    finding_scan = scan_wire_ends_on_pin_lines(
        path.read_bytes(),
        source_path="tests/fixtures/design_lint/near-miss-pin-line.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset({"R1.1"}),
    )
    candidate = next(
        item
        for item in schematic_geometry_candidates(finding_scan)
        if item.rule_id == "schematic.wire_end_on_pin_line"
    )

    with pytest.raises(ValueError, match="match their typed source projection"):
        replace(candidate, evidence={**candidate.evidence, "wire_uuid": ("stale-wire",)})
    with pytest.raises(ValueError, match="observation from its source scan"):
        WireEndOnPinLineSource(replace(finding_scan, findings=()), finding_scan.findings[0])
