"""Keep control-input requirements and coverage in their theme-owned model module."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    control_input_models,
    design_lint_candidate_inputs,
    design_lint_control_candidate_evidence,
    design_lint_control_candidates,
    design_lint_control_inputs,
)
from kicad_tooling.hwrepo import models as shared_models
from tests.lint_architecture_support import (
    IMPLEMENTATION_MAX_LINES,
    REPO_ROOT,
    line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint, pytest.mark.architecture]

CONTROL_INPUT_MODEL_NAMES = (
    "ControlInputBiasHeuristicEntry",
    "ControlInputBiasHeuristicCoverage",
    "ControlElectricalType",
    "ControlPinRequirement",
    "ControlBiasArrayChannelRequirement",
    "ControlBiasResistorArrayRequirement",
    "ControlBiasResistorRequirement",
    "ControlLocalBiasRequirement",
    "ControlInternalBiasRequirement",
    "ControlExternalBiasRequirement",
    "ControlNoBiasRequirement",
    "ControlBiasRequirement",
    "ControlSignalRequirement",
    "ControlInputsAnalysis",
)


def _top_level_definitions(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.update(target.id for target in targets if isinstance(target, ast.Name))
    return names


def test_control_input_models_live_in_owner_and_registry_exports_keep_identity() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/control_input_models.py"
    registry_path = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    registry_tree = ast.parse(registry_path.read_text(encoding="utf-8"))

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert set(CONTROL_INPUT_MODEL_NAMES) <= _top_level_definitions(owner_tree)
    registry_class_definitions = {
        node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)
    }
    assert not (set(CONTROL_INPUT_MODEL_NAMES) & registry_class_definitions)
    for name in CONTROL_INPUT_MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(control_input_models, name)


def test_internal_control_input_services_import_models_from_the_owner() -> None:
    legacy_imports: list[str] = []
    package = REPO_ROOT / "kicad_tooling"

    for source in sorted(package.rglob("*.py")):
        if source.name == "models.py":
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (node.module == "models" or node.module.endswith(".models"))
            ):
                legacy_imports.extend(
                    f"{source.relative_to(REPO_ROOT).as_posix()}:{alias.name}"
                    for alias in node.names
                    if alias.name in CONTROL_INPUT_MODEL_NAMES
                )

    assert not legacy_imports, (
        f"Internal control-input services must import theme-owned models directly: {legacy_imports}"
    )


def test_control_candidate_input_has_a_theme_owned_contract_module() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/design_lint_control_inputs.py"
    service_path = REPO_ROOT / "kicad_tooling/hwrepo/design_lint_control_candidates.py"
    bundle_path = REPO_ROOT / "kicad_tooling/hwrepo/design_lint_candidate_inputs.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    service_tree = ast.parse(service_path.read_text(encoding="utf-8"))
    bundle_tree = ast.parse(bundle_path.read_text(encoding="utf-8"))

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert "ControlCandidateInputs" in _top_level_definitions(owner_tree)
    assert "ControlCandidateInputs" not in _top_level_definitions(service_tree)
    for tree in (service_tree, bundle_tree):
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == "design_lint_control_inputs"
            and "ControlCandidateInputs" in {alias.name for alias in node.names}
            for node in tree.body
        )
    assert (
        design_lint_candidate_inputs.ControlCandidateInputs
        is design_lint_control_inputs.ControlCandidateInputs
    )
    assert (
        design_lint_control_candidates.ControlCandidateInputs
        is design_lint_control_inputs.ControlCandidateInputs
    )


def test_control_candidate_evidence_has_a_theme_owned_projection_module() -> None:
    evidence_path = REPO_ROOT / "kicad_tooling/hwrepo/design_lint_control_candidate_evidence.py"
    service_path = REPO_ROOT / "kicad_tooling/hwrepo/design_lint_control_candidates.py"
    evidence_tree = ast.parse(evidence_path.read_text(encoding="utf-8"))
    service_tree = ast.parse(service_path.read_text(encoding="utf-8"))

    assert line_count(evidence_path) < IMPLEMENTATION_MAX_LINES
    assert "ControlCandidate" in _top_level_definitions(evidence_tree)
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "project_control_candidate_evidence"
        for node in evidence_tree.body
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_control_candidate_evidence"
        and "ControlCandidate" in {alias.name for alias in node.names}
        for node in service_tree.body
    )
    assert (
        design_lint_control_candidates.ControlCandidate
        is design_lint_control_candidate_evidence.ControlCandidate
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"Candidate", "ControlCandidate"}
        for node in ast.walk(service_tree)
    )
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "evidence" for node in ast.walk(service_tree)
    )
