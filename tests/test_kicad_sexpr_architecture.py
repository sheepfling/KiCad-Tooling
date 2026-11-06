from __future__ import annotations

import ast
from pathlib import Path
from typing import get_type_hints

import pytest

from kicad_tooling.hwrepo.kicad_sexpr import SExprProperties, SExprSpan, sexpr_properties

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).resolve().parents[1]
_CONSUMERS = (
    "cad_assets.py",
    "cad_download.py",
    "cad_library.py",
    "cad_source.py",
    "cad_step.py",
    "cross_probe_board.py",
    "cross_probe_schematic.py",
    "model_inventory.py",
    "model_population.py",
    "part_cad.py",
    "pcb_drc_rule_parser.py",
    "schematic_geometry_scan.py",
    "schematic_geometry_source.py",
    "schematic_obstruction_geometry.py",
    "schematic_symbol_geometry.py",
    "schematic_text_geometry.py",
    "schematic_wire_geometry.py",
    "test_access.py",
)
_PARSER_HELPERS = {
    "_Span",
    "_Token",
    "_atoms",
    "_children",
    "_field",
    "_nodes",
    "_properties",
    "_property",
    "_quote",
    "_root",
    "_scalar",
    "_tokens",
}


def _imports(path: Path) -> tuple[ast.ImportFrom, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return tuple(node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))


def test_property_index_annotation_names_the_parser_contract() -> None:
    assert get_type_hints(sexpr_properties)["return"] == SExprProperties
    assert SExprSpan.__dataclass_params__.frozen
    assert SExprSpan.__slots__ == ("start", "end")


def test_shared_parser_consumers_import_from_the_parser_owner() -> None:
    package = _ROOT / "kicad_tooling/hwrepo"
    for filename in _CONSUMERS:
        assert any(
            node.module == "kicad_sexpr"
            or (node.module is None and any(alias.name == "kicad_sexpr" for alias in node.names))
            for node in _imports(package / filename)
        ), filename


def test_parser_helpers_do_not_flow_through_service_modules() -> None:
    package = _ROOT / "kicad_tooling/hwrepo"
    for filename in _CONSUMERS:
        for node in _imports(package / filename):
            if node.module not in {"model_inventory", "part_cad"}:
                continue
            imported = {alias.name for alias in node.names}
            assert imported.isdisjoint(_PARSER_HELPERS), filename


def test_parser_owner_stays_within_the_review_size() -> None:
    parser = _ROOT / "kicad_tooling/hwrepo/kicad_sexpr.py"
    assert len(parser.read_text(encoding="utf-8").splitlines()) < 500
