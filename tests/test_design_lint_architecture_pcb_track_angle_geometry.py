"""Guard ownership, source wiring, and reviewable sizes for track-angle geometry lint."""

from __future__ import annotations

import ast
import json

import pytest

from tests.lint_architecture_support import HWREPO

RULE_ID = "pcb.track_angle_geometry_review"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.catalog_lint,
    pytest.mark.pcb_lint,
    pytest.mark.architecture,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_track_angle_geometry_modules_and_regressions_stay_reviewable() -> None:
    module_paths = (
        "pcb_track_angle_geometry.py",
        "design_lint_pcb_track_angle_geometry_scan.py",
        "design_lint_pcb_geometry_modes.py",
        "design_lint_pcb_geometry_scan.py",
    )
    test_paths = (
        "tests/test_pcb_track_angle_geometry.py",
        "tests/test_pcb_track_angle_geometry_native_fixture_lane.py",
        "tests/test_pcb_track_angle_geometry_mcp_parity.py",
        "tests/test_design_lint_architecture_pcb_track_angle_geometry.py",
    )
    sizes = {
        path: len((HWREPO / path).read_text(encoding="utf-8").splitlines())
        if not path.startswith("tests/")
        else len((HWREPO.parent.parent / path).read_text(encoding="utf-8").splitlines())
        for path in (*module_paths, *test_paths)
    }

    assert all(size < 500 for size in sizes.values()), sizes


def test_catalog_owner_is_the_theme_predicate_and_reaches_project_inspection() -> None:
    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    rule = next(item for item in catalog["rules"] if item["rule_id"] == RULE_ID)
    owner_path, owner_function = rule["implementation_owner"].split("#", 1)
    owner_source = ast.parse((HWREPO.parent.parent / owner_path).read_text(encoding="utf-8"))
    owner_functions = {item.name for item in owner_source.body if isinstance(item, ast.FunctionDef)}
    scan_source = ast.parse(
        (HWREPO / "design_lint_pcb_track_angle_geometry_scan.py").read_text(encoding="utf-8")
    )
    scan_imports = {
        alias.name
        for node in scan_source.body
        if isinstance(node, ast.ImportFrom) and node.module == "pcb_track_angle_geometry"
        for alias in node.names
    }
    project_source = (HWREPO / "design_lint_project_inspection.py").read_text(encoding="utf-8")
    geometry_scan = (HWREPO / "design_lint_pcb_geometry_scan.py").read_text(encoding="utf-8")

    assert rule["theme"] == "pcb"
    assert rule["default_mode"] == "off"
    assert owner_function == "track_angle_geometry_violations"
    assert owner_function in owner_functions
    assert rule["implementation_owner"] in rule["implementation_refs"]
    assert "track_angle_geometry_candidates" in scan_imports
    assert "track_angle_geometry_scan_required" in geometry_scan
    assert "pcb_track_angle_geometry_candidates" in project_source
    assert "pcb_source_candidates" in project_source
