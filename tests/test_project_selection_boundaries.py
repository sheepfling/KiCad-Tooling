"""Single-project lookup is shared while adapters retain their guidance."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo import (
    contract_coach,
    design_lint,
    electrical,
    electrical_setup,
    mcp_workflow_paths,
    part_cad,
    selection,
)
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.synthetic_design_lint_project import synthetic_design_lint_project


def test_registered_project_resolves_for_services_and_mcp(tmp_path: Path) -> None:
    root, _ = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    project = selection.resolve_project(root, "controller")
    assert project.id == "controller"
    assert mcp_workflow_paths.selected_project(root, "controller") == project
    assert electrical.selected_config(root, "controller").project_id == project.id


def test_missing_project_preserves_each_operation_error(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    with pytest.raises(selection.UnknownProjectError, match="Unknown project 'missing'") as error:
        selection.resolve_project(root, "missing")
    assert error.value.project_id == "missing"
    for operation in (
        electrical.selected_config,
        contract_coach.project_context,
        part_cad.read_cad_components,
    ):
        with pytest.raises(selection.UnknownProjectError, match="Unknown project 'missing'"):
            operation(root, "missing")
    with pytest.raises(ValueError, match="Unknown project ID: missing. Call list_projects first"):
        mcp_workflow_paths.selected_project(root, "missing")
    lint = design_lint.inspect_summary(root, "missing", native)
    assert lint.status == "BLOCKED"
    assert lint.issues == ("Unknown project 'missing'",)


def test_mcp_does_not_relabel_registry_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_registry(_root: Path) -> selection.ProjectRegistry:
        raise ValueError("Invalid project discovery configuration")

    monkeypatch.setattr(selection, "load_registry", broken_registry)
    with pytest.raises(ValueError, match="Invalid project discovery configuration"):
        mcp_workflow_paths.selected_project(tmp_path, "controller")


@pytest.mark.parametrize(
    "operation", [electrical_setup.initialize, electrical_setup.capture_inputs]
)
def test_project_removed_between_selection_and_electrical_setup_has_typed_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: object
) -> None:
    root, _ = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    registry = selection.load_registry(root)
    states = iter((registry, registry.model_copy(update={"projects": ()})))

    def changing_registry(_root: Path) -> selection.ProjectRegistry:
        return next(states)

    monkeypatch.setattr(selection, "load_registry", changing_registry)
    with pytest.raises(selection.UnknownProjectError, match="Unknown project 'controller'"):
        if operation is electrical_setup.initialize:
            electrical_setup.initialize(root, "controller")
        else:
            electrical_setup.capture_inputs(root, "controller")
