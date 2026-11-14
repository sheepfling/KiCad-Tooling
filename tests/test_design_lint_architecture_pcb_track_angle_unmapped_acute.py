"""Guard the acute-corner rule owner, geometry scan wiring, and review limits."""

from __future__ import annotations

import ast
import json

import pytest

from tests.lint_architecture_support import HWREPO

RULE_ID = "pcb.unmapped_acute_track_corner_review"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.catalog_lint,
    pytest.mark.pcb_lint,
    pytest.mark.architecture,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_rule_owner_is_the_pcb_geometry_predicate_and_is_reached_by_scan() -> None:
    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    rule = next(item for item in catalog["rules"] if item["rule_id"] == RULE_ID)
    owner_path, owner_function = rule["implementation_owner"].split("#", 1)
    owner_source = ast.parse((HWREPO.parent.parent / owner_path).read_text(encoding="utf-8"))
    owner_functions = {node.name for node in owner_source.body if isinstance(node, ast.FunctionDef)}
    scan_source = ast.parse(
        (HWREPO / "design_lint_pcb_track_angle_geometry_scan.py").read_text(encoding="utf-8")
    )
    scan_imports = {
        alias.name
        for node in scan_source.body
        if isinstance(node, ast.ImportFrom) and node.module == "pcb_track_angle_unmapped_geometry"
        for alias in node.names
    }

    assert rule["theme"] == "pcb"
    assert rule["default_mode"] == "off"
    assert owner_function == "unmapped_acute_track_corner_candidates"
    assert owner_function in owner_functions
    assert rule["implementation_owner"] in rule["implementation_refs"]
    assert "unmapped_acute_track_corner_candidates" in scan_imports
    assert "track_angle_geometry_candidates_for_scan" in {
        node.name for node in scan_source.body if isinstance(node, ast.FunctionDef)
    }


def test_new_rule_and_related_regression_modules_stay_reviewable() -> None:
    module_paths = (
        "pcb_track_angle_geometry.py",
        "pcb_track_angle_unmapped_geometry.py",
        "design_lint_pcb_track_angle_geometry_scan.py",
    )
    test_paths = (
        "tests/test_pcb_track_angle_unmapped_acute.py",
        "tests/test_pcb_track_angle_geometry_mcp_parity.py",
        "tests/test_pcb_track_angle_geometry_native_fixture_lane.py",
        "tests/test_design_lint_architecture_pcb_track_angle_unmapped_acute.py",
    )
    sizes = {
        path: len((HWREPO / path).read_text(encoding="utf-8").splitlines())
        if not path.startswith("tests/")
        else len((HWREPO.parent.parent / path).read_text(encoding="utf-8").splitlines())
        for path in (*module_paths, *test_paths)
    }

    assert all(size < 500 for size in sizes.values()), sizes


def test_acute_rule_remains_pcb_only_and_has_an_explicit_threshold() -> None:
    project_models = (HWREPO / "project_models.py").read_text(encoding="utf-8")
    owner = (HWREPO / "pcb_track_angle_unmapped_geometry.py").read_text(encoding="utf-8")

    assert project_models.count('"pcb.unmapped_acute_track_corner_review"') >= 2
    assert "_ACUTE_CORNER_THRESHOLD_MILLIDEGREES = 89_000" in owner
    assert "SUPPORTED_TRACK_ANGLE_KICAD_VERSIONS" in owner
    assert "item.angle_millidegrees < _ACUTE_CORNER_THRESHOLD_MILLIDEGREES" in owner
