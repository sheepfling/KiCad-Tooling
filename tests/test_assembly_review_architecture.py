"""Keep the assembly viewer's generated JSON boundary explicitly typed."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

REPOSITORY_ROOT = Path(__file__).parents[1]


def test_assembly_viewer_json_payload_has_named_fields_and_no_opaque_object_map() -> None:
    path = REPOSITORY_ROOT / "kicad_tooling/hwrepo/assembly_review_html.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    config = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "AssemblyViewerConfig"
    )
    fields = {
        statement.target.id
        for statement in config.body
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
    }

    assert fields == {
        "board_unit",
        "enclosure_unit",
        "translation_mm",
        "rotation_xyzw",
    }
    assert "config: dict[str, object]" not in source
    assert 'json.dumps(config, separators=(",", ":"))' in source
