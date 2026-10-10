"""Keep schematic geometry lint separated by source and behavior."""

from __future__ import annotations

import pytest

from tests.lint_architecture_support import (
    FACADE_MAX_LINES,
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
)
from tests.lint_architecture_support import (
    line_count as _line_count,
)

pytestmark = pytest.mark.design_lint

SCHEMATIC_GEOMETRY_MODULES = (
    "schematic_geometry_types.py",
    "schematic_geometry_source.py",
    "schematic_geometry_primitives.py",
    "schematic_symbol_geometry.py",
    "schematic_pin_geometry.py",
    "schematic_wire_geometry.py",
    "schematic_text_geometry.py",
    "schematic_obstruction_geometry.py",
    "schematic_geometry_scan.py",
    "schematic_geometry_tree.py",
)


def test_schematic_geometry_stays_split_by_responsibility() -> None:
    facade = HWREPO / "schematic_geometry.py"
    modules = [HWREPO / name for name in SCHEMATIC_GEOMETRY_MODULES]

    assert _line_count(facade) < FACADE_MAX_LINES
    assert all(path.is_file() for path in modules)
    module_sizes = {path.name: _line_count(path) for path in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }

    assert not oversized, (
        "Keep schematic geometry parsing, check themes, and scan coordination in "
        f"reviewable modules below 500 lines; oversized modules: {oversized}"
    )


def test_schematic_geometry_rule_refs_point_to_the_owning_modules() -> None:
    catalog = HWREPO / "design-lint-rules.json"

    assert "kicad_tooling/hwrepo/schematic_geometry.py#" not in catalog.read_text(encoding="utf-8")
