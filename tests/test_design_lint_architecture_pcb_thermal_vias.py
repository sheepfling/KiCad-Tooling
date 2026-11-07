"""Guard PCB thermal-via rule ownership, report models, and module sizes."""

from __future__ import annotations

import ast
from typing import get_type_hints

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo import (
    design_lint_policy_models,
    pcb_thermal_via_models,
    pcb_thermal_vias,
    project_models,
)
from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count
from tests.pcb_thermal_vias_support import mapping

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_thermal_via_rule_has_one_theme_owned_predicate() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == "pcb.thermal_via_coverage")
    service_path = HWREPO / "pcb_thermal_vias.py"
    service_tree = ast.parse(service_path.read_text(encoding="utf-8"))
    service_imports = {
        alias.name
        for node in ast.walk(service_tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert rule.theme == "pcb"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/pcb_thermal_vias.py#pcb_thermal_via_entries"
    )
    assert pcb_thermal_vias.pcb_thermal_via_entries.__module__ == pcb_thermal_vias.__name__
    assert "PcbThermalViaMap" in service_imports
    assert "kicad_tooling/hwrepo/pcb_thermal_vias.py#pcb_thermal_via_entries" in (
        rule.implementation_refs
    )


def test_thermal_via_policy_uses_theme_models_without_growing_compat_registry() -> None:
    policy_types = get_type_hints(design_lint_policy_models.DesignLintPolicy)
    assert policy_types["pcb_thermal_via_map"] == pcb_thermal_via_models.PcbThermalViaMap | None
    compatibility_text = (HWREPO / "models.py").read_text(encoding="utf-8")
    assert "PcbThermalVia" not in compatibility_text


def test_thermal_via_modules_stay_below_review_ceiling() -> None:
    modules = (
        "pcb_thermal_via_models.py",
        "pcb_thermal_vias.py",
        "design_lint_pcb_thermal_via_candidate_evidence.py",
        "design_lint_pcb_thermal_via_scan.py",
    )
    assert all(line_count(HWREPO / name) < IMPLEMENTATION_MAX_LINES for name in modules)


def test_thermal_via_maps_require_an_authoritative_pcb_project() -> None:
    policy = design_lint_policy_models.DesignLintPolicy(pcb_thermal_via_map=mapping())
    ignored = project_models.IgnoredChecks(erc=(), drc=())
    schematic_validation = project_models.SchematicValidationContract(
        kind=project_models.ProjectKind.SCHEMATIC,
        expected_ignored_checks=ignored,
    )
    with pytest.raises(ValidationError, match="authoritative PCB project"):
        project_models.ProjectConfig(
            schema_version="1",
            kind=project_models.ProjectKind.SCHEMATIC,
            assurance_profile="development",
            not_for_manufacture=True,
            project_id="synthetic-schematic",
            component_identity=project_models.ComponentIdentity(required=False, part_ids=()),
            toolchain_id="synthetic-kicad-10",
            kicad_version="10.0.5",
            image="example.invalid/kicad:10.0.5",
            project="projects/schematic/schematic.kicad_pro",
            source_roots=("projects/schematic",),
            required_inputs=(),
            validation=schematic_validation,
            design_lint=policy,
        )
    with pytest.raises(ValidationError, match="authoritative PCB project"):
        project_models.ProjectTestContract(
            validation=schematic_validation,
            design_lint=policy,
        )
