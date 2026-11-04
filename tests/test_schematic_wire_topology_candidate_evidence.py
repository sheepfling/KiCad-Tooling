"""Typed source regressions for schematic wire-topology candidates."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_schematic_geometry import schematic_geometry_candidates
from kicad_tooling.hwrepo.design_lint_schematic_geometry_candidate_evidence import (
    SchematicWireTopologyCandidate,
    UnmarkedTJunctionSource,
    UnmarkedWireCrossingSource,
)
from kicad_tooling.hwrepo.schematic_geometry import scan_wire_ends_on_pin_lines

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
]

_FIXTURES = Path(__file__).parent / "fixtures/design_lint"


@pytest.mark.parametrize(
    ("filename", "source_path", "rule_id", "source_type", "scan_attribute", "pins"),
    (
        (
            "unmarked-orthogonal-crossing.kicad_sch",
            "tests/fixtures/design_lint/unmarked-orthogonal-crossing.kicad_sch",
            "schematic.unmarked_wire_crossing",
            UnmarkedWireCrossingSource,
            "unmarked_wire_crossings",
            frozenset[str](),
        ),
        (
            "t-junction/fault-no-junction.kicad_sch",
            "tests/fixtures/design_lint/t-junction/fault-no-junction.kicad_sch",
            "schematic.unmarked_t_junction",
            UnmarkedTJunctionSource,
            "unmarked_t_junctions",
            frozenset({"R1.2"}),
        ),
    ),
)
def test_wire_topology_candidate_retains_its_scan_observation(
    filename: str,
    source_path: str,
    rule_id: str,
    source_type: type[UnmarkedWireCrossingSource | UnmarkedTJunctionSource],
    scan_attribute: str,
    pins: frozenset[str],
) -> None:
    scan = scan_wire_ends_on_pin_lines(
        (_FIXTURES / filename).read_bytes(),
        source_path=source_path,
        kicad_version="10.0.6",
        unconnected_pins=pins,
    )

    candidate = next(
        item for item in schematic_geometry_candidates(scan) if item.rule_id == rule_id
    )

    assert isinstance(candidate, SchematicWireTopologyCandidate)
    assert isinstance(candidate.source_evidence, source_type)
    assert candidate.source_evidence.scan is scan
    assert candidate.source_evidence.finding is getattr(scan, scan_attribute)[0]
    assert candidate.evidence["schematic_sha256"] == (scan.source_sha256,)
    assert candidate.evidence["sheet_instance_path"] == (
        candidate.source_evidence.finding.sheet_instance_path,
    )


def test_wire_topology_candidate_rejects_projection_drift_and_detached_source() -> None:
    path = _FIXTURES / "unmarked-orthogonal-crossing.kicad_sch"
    scan = scan_wire_ends_on_pin_lines(
        path.read_bytes(),
        source_path="tests/fixtures/design_lint/unmarked-orthogonal-crossing.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    candidate = next(
        item
        for item in schematic_geometry_candidates(scan)
        if item.rule_id == "schematic.unmarked_wire_crossing"
    )

    with pytest.raises(ValueError, match="match their typed source projection"):
        replace(candidate, evidence={**candidate.evidence, "wire_uuids": ("stale-wire",)})
    with pytest.raises(ValueError, match="observation from its source scan"):
        UnmarkedWireCrossingSource(
            replace(scan, unmarked_wire_crossings=()), scan.unmarked_wire_crossings[0]
        )
