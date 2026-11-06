"""Keep schematic source parser outputs named by their geometry domain."""

from __future__ import annotations

import hashlib
import json

import pytest

from kicad_tooling.hwrepo.schematic_geometry_models import SchematicInstanceReferenceResolution
from kicad_tooling.hwrepo.schematic_geometry_source import (
    SchematicSourceDocument,
    schematic_instance_references,
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
from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    REPEATED_CHANNEL,
    UNMARKED_CROSSING,
)

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


def test_instance_reference_resolution_is_typed_read_only_and_source_bound() -> None:
    source = REPEATED_CHANNEL.read_bytes()
    document = schematic_root(source)
    project_name = "repeated-sheet-root"
    sheet_instance_path = (
        "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000002"
    )

    result = schematic_instance_references(
        document.text,
        document.root,
        source_path=REPEATED_CHANNEL.as_posix(),
        project_name=project_name,
        sheet_instance_path=sheet_instance_path,
    )

    assert isinstance(result, SchematicInstanceReferenceResolution)
    assert result.source_path == REPEATED_CHANNEL.as_posix()
    assert result.source_sha256 == hashlib.sha256(source).hexdigest()
    assert result.project_name == project_name
    assert result.sheet_instance_path == sheet_instance_path
    assert result.references_by_symbol_uuid == {"b0000000-0000-4000-8000-000000000002": "R1"}
    assert result.model_dump()["references_by_symbol_uuid"] == {
        "b0000000-0000-4000-8000-000000000002": "R1"
    }
    assert json.loads(result.model_dump_json())["references_by_symbol_uuid"] == {
        "b0000000-0000-4000-8000-000000000002": "R1"
    }
    assert result.issues == ()
    with pytest.raises(TypeError):
        result.references_by_symbol_uuid["new-symbol"] = "R99"

    unresolved = schematic_instance_references(
        document.text,
        document.root,
        source_path=REPEATED_CHANNEL.as_posix(),
        project_name="another-project",
        sheet_instance_path=sheet_instance_path,
    )
    assert unresolved.references_by_symbol_uuid == {}
    assert len(unresolved.issues) == 1
