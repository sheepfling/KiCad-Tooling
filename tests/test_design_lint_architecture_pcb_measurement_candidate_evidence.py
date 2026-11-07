"""Guard typed ownership of PCB measurement candidate evidence."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    design_lint_pcb_decoupling_candidate_evidence,
    design_lint_pcb_protection_path_candidate_evidence,
    design_lint_pcb_reference_plane_candidate_evidence,
    design_lint_pcb_thermal_via_candidate_evidence,
    design_lint_pcb_track_width_candidate_evidence,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
]


_OWNER_MODULES = (
    "design_lint_pcb_decoupling_candidate_evidence.py",
    "design_lint_pcb_protection_path_candidate_evidence.py",
    "design_lint_pcb_track_width_candidate_evidence.py",
    "design_lint_pcb_reference_plane_candidate_evidence.py",
    "design_lint_pcb_thermal_via_candidate_evidence.py",
)


def test_measurement_candidate_translator_routes_each_rule_to_its_theme_owner() -> None:
    translator_path = HWREPO / "design_lint_pcb_measurement_candidates.py"
    translator_tree = ast.parse(translator_path.read_text(encoding="utf-8"))
    translator = next(
        node
        for node in translator_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "pcb_measurement_coverage_candidates"
    )
    typed_owners = {
        node.func.value.id
        for node in ast.walk(translator)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
        and isinstance(node.func.value, ast.Name)
    }

    assert typed_owners == {
        "PcbDecouplingCandidate",
        "PcbProtectionPathCandidate",
        "PcbTrackWidthCandidate",
        "PcbReferencePlaneCandidate",
        "PcbThermalViaCandidate",
    }
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        for node in ast.walk(translator)
    )
    for filename in (*_OWNER_MODULES, "design_lint_pcb_measurement_candidates.py"):
        assert line_count(HWREPO / filename) < IMPLEMENTATION_MAX_LINES


def test_measurement_candidate_types_and_projectors_have_theme_owned_modules() -> None:
    owners = (
        (
            design_lint_pcb_decoupling_candidate_evidence,
            design_lint_pcb_decoupling_candidate_evidence.PcbDecouplingCandidate,
            "project_pcb_decoupling_evidence",
        ),
        (
            design_lint_pcb_protection_path_candidate_evidence,
            design_lint_pcb_protection_path_candidate_evidence.PcbProtectionPathCandidate,
            "project_pcb_protection_path_evidence",
        ),
        (
            design_lint_pcb_track_width_candidate_evidence,
            design_lint_pcb_track_width_candidate_evidence.PcbTrackWidthCandidate,
            "project_pcb_track_width_evidence",
        ),
        (
            design_lint_pcb_reference_plane_candidate_evidence,
            design_lint_pcb_reference_plane_candidate_evidence.PcbReferencePlaneCandidate,
            "project_pcb_reference_plane_evidence",
        ),
        (
            design_lint_pcb_thermal_via_candidate_evidence,
            design_lint_pcb_thermal_via_candidate_evidence.PcbThermalViaCandidate,
            "project_pcb_thermal_via_evidence",
        ),
    )

    for module, candidate_type, projector_name in owners:
        owner_path = HWREPO / f"{module.__name__.rsplit('.', 1)[-1]}.py"
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
        assert candidate_type.__module__ == module.__name__
        assert any(
            isinstance(node, ast.FunctionDef) and node.name == projector_name
            for node in owner_tree.body
        )
