"""Keep schematic source parser outputs named by their geometry domain."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.schematic_geometry_source import (
    SchematicSourceDocument,
    schematic_root,
)
from kicad_tooling.hwrepo.schematic_wire_geometry import (
    SchematicJunctionGeometryResult,
    SchematicLabelAnchorResult,
    SchematicWireGeometryResult,
    junction_points,
    label_anchors,
    wire_geometry,
)
from tests.design_lint_fixtures.schematic_geometry_fixtures import UNMARKED_CROSSING

pytestmark = [pytest.mark.design_lint, pytest.mark.schematic_lint]


def test_schematic_geometry_parsers_return_named_records_and_issues() -> None:
    document = schematic_root(UNMARKED_CROSSING.read_bytes())
    text = document.text
    root = document.root

    assert isinstance(document, SchematicSourceDocument)
    wires = wire_geometry(text, root)
    junctions = junction_points(text, root)
    labels = label_anchors(text, root)

    assert isinstance(wires, SchematicWireGeometryResult)
    assert len(wires.wire_ends) == 6
    assert len(wires.wire_segments) == 3
    assert wires.unsupported_reasons == ()
    assert isinstance(junctions, SchematicJunctionGeometryResult)
    assert junctions.unsupported_reasons == ()
    assert isinstance(labels, SchematicLabelAnchorResult)
    assert labels.unsupported_reasons == ()


def test_schematic_geometry_records_retain_unsupported_parse_reasons() -> None:
    document = schematic_root(
        b"""(kicad_sch
  (wire (pts (xy 0 0) (xy 1 1)))
  (junction)
  (label "UNANCHORED" (uuid "b0000000-0000-4000-8000-000000000001"))
)"""
    )

    wires = wire_geometry(document.text, document.root)
    junctions = junction_points(document.text, document.root)
    labels = label_anchors(document.text, document.root)

    assert wires.unsupported_reasons == ("wire without a unique UUID or point list",)
    assert junctions.unsupported_reasons == (
        "junction unknown has invalid location: Expected exactly one at field in KiCad schematic",
    )
    expected_label_reason = (
        "label b0000000-0000-4000-8000-000000000001 has invalid anchor: "
        "Expected exactly one at field in KiCad schematic"
    )
    assert labels.unsupported_reasons == (expected_label_reason,)
