"""Guard fiducial lint ownership, configuration, evidence, and module size."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo import design_lint_policy_models, pcb_fiducial_models, pcb_fiducials
from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from kicad_tooling.hwrepo.project_models import (
    ComponentIdentity,
    IgnoredChecks,
    ProjectConfig,
    ProjectKind,
    SchematicValidationContract,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count
from tests.pcb_fiducials_support import requirement_map

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_fiducial_rule_has_one_pcb_owned_count_predicate() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == "pcb.fiducial_count")
    owner = "kicad_tooling/hwrepo/pcb_fiducials.py#pcb_fiducial_entries"

    assert rule.theme == "pcb"
    assert rule.default_mode == "review"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
    assert pcb_fiducials.pcb_fiducial_entries.__module__ == pcb_fiducials.__name__


def test_fiducial_models_stay_in_their_theme_and_modules_below_review_limit() -> None:
    policy_types = design_lint_policy_models.DesignLintPolicy.model_fields
    assert policy_types["pcb_fiducial_map"].annotation == pcb_fiducial_models.PcbFiducialMap | None
    compatibility_text = (HWREPO / "models.py").read_text(encoding="utf-8")
    assert "PcbFiducial" not in compatibility_text
    modules = (
        "pcb_fiducial_models.py",
        "pcb_fiducials.py",
        "design_lint_pcb_fiducial_scan.py",
        "design_lint_pcb_fiducial_candidate_evidence.py",
        "design_lint_pcb_fiducial_candidates.py",
        "design_lint_pcb_fiducial_report.py",
    )
    assert all(line_count(HWREPO / name) < IMPLEMENTATION_MAX_LINES for name in modules)


def test_fiducial_map_requires_an_authoritative_pcb_project() -> None:
    policy = design_lint_policy_models.DesignLintPolicy(pcb_fiducial_map=requirement_map())
    validation = SchematicValidationContract(
        kind=ProjectKind.SCHEMATIC,
        expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
    )

    with pytest.raises(ValidationError, match="authoritative PCB project"):
        ProjectConfig(
            schema_version="1",
            kind=ProjectKind.SCHEMATIC,
            assurance_profile="development",
            not_for_manufacture=True,
            project_id="synthetic-schematic",
            component_identity=ComponentIdentity(required=False, part_ids=()),
            toolchain_id="synthetic-kicad-10",
            kicad_version="10.0.5",
            image="example.invalid/kicad:10.0.5",
            project="projects/schematic/schematic.kicad_pro",
            source_roots=("projects/schematic",),
            required_inputs=(),
            validation=validation,
            design_lint=policy,
        )
