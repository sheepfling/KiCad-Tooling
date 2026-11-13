"""Guard track-angle models, rule ownership, and module boundaries."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.pcb_track_angle_models import PcbTrackAngleMap
from tests.lint_architecture_support import HWREPO

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.catalog_lint,
    pytest.mark.pcb_lint,
    pytest.mark.architecture,
]


def test_track_angle_modules_keep_theme_ownership_and_reviewable_size() -> None:
    names = (
        "pcb_drc_conditions.py",
        "pcb_track_angle.py",
        "pcb_track_angle_unmapped.py",
        "pcb_track_angle_models.py",
    )
    sizes = {name: len((HWREPO / name).read_text(encoding="utf-8").splitlines()) for name in names}

    assert all(size < 500 for size in sizes.values()), sizes
    assert DesignLintPolicy.model_fields["pcb_track_angle_map"].annotation in {
        PcbTrackAngleMap | None,
    }


def test_track_angle_model_is_not_reexported_from_shared_models() -> None:
    source = (HWREPO / "models.py").read_text(encoding="utf-8")

    assert "PcbTrackAngleMap" not in source
    assert "PcbTrackAngleRequirement" not in source


def test_track_angle_service_owns_the_rule_predicate_and_integration() -> None:
    catalog = (HWREPO / "design-lint-rules.json").read_text(encoding="utf-8")
    service = ast.parse((HWREPO / "pcb_track_angle.py").read_text(encoding="utf-8"))
    functions = {node.name for node in service.body if isinstance(node, ast.FunctionDef)}
    inspection = ast.parse(
        (HWREPO / "design_lint_project_inspection.py").read_text(encoding="utf-8")
    )
    imports = {
        alias.name
        for node in inspection.body
        if isinstance(node, ast.ImportFrom) and node.module == "pcb_track_angle"
        for alias in node.names
    }

    assert "track_angle_rule_coverage_issue" in functions
    assert "track_angle_rule_coverage_candidates" in functions
    assert "track_angle_rule_coverage_candidates" in imports
    assert "kicad_tooling/hwrepo/pcb_track_angle.py#track_angle_rule_coverage_issue" in catalog
    unmapped = ast.parse((HWREPO / "pcb_track_angle_unmapped.py").read_text(encoding="utf-8"))
    unmapped_functions = {node.name for node in unmapped.body if isinstance(node, ast.FunctionDef)}
    assert "unmapped_track_angle_rule_candidates" in unmapped_functions
    assert (
        "kicad_tooling/hwrepo/pcb_track_angle_unmapped.py#unmapped_track_angle_rule_candidates"
        in catalog
    )
    assert (
        "kicad_tooling/hwrepo/pcb_drc_conditions.py#native_net_conditions_are_disjoint" in catalog
    )


def test_track_angle_policy_is_rejected_for_non_pcb_projects() -> None:
    project_models = (HWREPO / "project_models.py").read_text(encoding="utf-8")

    assert project_models.count("self.design_lint.pcb_track_angle_map is not None") == 2
