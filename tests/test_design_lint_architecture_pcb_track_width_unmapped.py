"""Guard native track-width scope review ownership and module boundaries."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.pcb_track_width_models import PcbTrackWidthMap
from tests.lint_architecture_support import HWREPO, TESTS

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.catalog_lint,
    pytest.mark.pcb_lint,
    pytest.mark.architecture,
]


def test_track_width_scope_modules_stay_theme_owned_and_reviewable() -> None:
    production = (
        "pcb_drc_conditions.py",
        "pcb_track_width_models.py",
        "pcb_track_width_unmapped.py",
        "pcb_track_width_rule_coverage.py",
    )
    regressions = (
        "test_pcb_track_width_unmapped_rules.py",
        "test_design_lint_mcp_parity_pcb_track_width_unmapped.py",
        "pcb_drc_parity_support.py",
        "design_lint_pcb_track_width_rule_selector_cases.py",
    )
    sizes = {
        name: len(path.read_text(encoding="utf-8").splitlines())
        for names, directory in ((production, HWREPO), (regressions, TESTS))
        for name in names
        for path in (directory / name,)
    }

    assert all(size < 500 for size in sizes.values()), sizes
    assert DesignLintPolicy.model_fields["pcb_track_width_map"].annotation in {
        PcbTrackWidthMap | None,
    }


def test_track_width_scope_predicate_and_scanner_own_the_catalog_rule() -> None:
    catalog = (HWREPO / "design-lint-rules.json").read_text(encoding="utf-8")
    predicate = ast.parse((HWREPO / "pcb_track_width_unmapped.py").read_text(encoding="utf-8"))
    scanner = ast.parse((HWREPO / "pcb_track_width_rule_coverage.py").read_text(encoding="utf-8"))
    inspection = ast.parse(
        (HWREPO / "design_lint_project_inspection.py").read_text(encoding="utf-8")
    )
    predicate_names = {node.name for node in predicate.body if isinstance(node, ast.FunctionDef)}
    scanner_names = {node.name for node in scanner.body if isinstance(node, ast.FunctionDef)}
    inspection_imports = {
        alias.name
        for node in inspection.body
        if isinstance(node, ast.ImportFrom) and node.module == "pcb_track_width_rule_coverage"
        for alias in node.names
    }

    assert "unmapped_track_width_rule_candidates" in predicate_names
    assert "track_width_rule_scope_candidates" in scanner_names
    assert "track_width_rule_scope_candidates" in inspection_imports
    assert (
        "kicad_tooling/hwrepo/pcb_track_width_unmapped.py#unmapped_track_width_rule_candidates"
    ) in catalog
    assert (
        "kicad_tooling/hwrepo/pcb_track_width_rule_coverage.py#track_width_rule_scope_candidates"
    ) in catalog
