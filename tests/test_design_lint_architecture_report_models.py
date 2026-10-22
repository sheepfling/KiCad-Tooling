"""Architecture guards for the focused design-lint report model owner."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import get_args

import pytest

from kicad_tooling.hwrepo import (
    design_lint_connectivity_snapshot_models,
    design_lint_mapped_topology_models,
    design_lint_report_models,
    models,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]

REPOSITORY = Path(__file__).resolve().parents[1]
TOOLING = REPOSITORY / "kicad_tooling"
OWNER = TOOLING / "hwrepo" / "design_lint_report_models.py"


def test_design_lint_report_owner_stays_below_review_limit() -> None:
    assert len(OWNER.read_text(encoding="utf-8").splitlines()) < 500


def test_internal_services_import_report_from_its_owner() -> None:
    legacy_imports: list[str] = []
    for path in TOOLING.rglob("*.py"):
        if path == TOOLING / "hwrepo" / "models.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            is_compatibility_registry = node.module in {"models", "hwrepo.models"} or (
                node.module.endswith(".models") and not node.module.endswith("_models")
            )
            if is_compatibility_registry and any(
                alias.name in {"DesignLintReport", "DesignLintMappedCheckRun"}
                for alias in node.names
            ):
                legacy_imports.append(path.relative_to(REPOSITORY).as_posix())

    assert not legacy_imports, f"Internal services use the compatibility registry: {legacy_imports}"


def test_models_compatibility_export_and_forward_field_use_the_owner() -> None:
    assert models.DesignLintReport is design_lint_report_models.DesignLintReport
    annotation = models.ProjectVerificationReport.model_fields["design_lint"].annotation
    assert design_lint_report_models.DesignLintReport in get_args(annotation)

    model_tree = ast.parse((TOOLING / "hwrepo" / "models.py").read_text(encoding="utf-8"))
    local_report_definitions = [
        node.name
        for node in model_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DesignLintReport"
    ]
    assert local_report_definitions == []


def test_mapped_topology_execution_model_has_a_focused_owner_and_compatible_export() -> None:
    owner = TOOLING / "hwrepo" / "design_lint_mapped_topology_models.py"
    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert (
        models.DesignLintMappedCheckRun
        is design_lint_mapped_topology_models.DesignLintMappedCheckRun
    )

    model_tree = ast.parse((TOOLING / "hwrepo" / "models.py").read_text(encoding="utf-8"))
    local_model_definitions = [
        node.name
        for node in model_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DesignLintMappedCheckRun"
    ]
    assert local_model_definitions == []
    assert design_lint_mapped_topology_models.DesignLintMappedCheckRun in get_args(
        design_lint_report_models.DesignLintReport.model_fields["mapped_check_runs"].annotation
    )


def test_connectivity_snapshot_owners_stay_bounded_and_theme_owned() -> None:
    owners = {
        "design_lint_connectivity_snapshot.py",
        "design_lint_connectivity_snapshot_models.py",
    }
    for name in owners:
        path = TOOLING / "hwrepo" / name
        assert len(path.read_text(encoding="utf-8").splitlines()) < 500

    report_source = (TOOLING / "hwrepo" / "design_lint_report_models.py").read_text(
        encoding="utf-8"
    )
    reconciliation_source = (TOOLING / "hwrepo" / "design_lint_reconciliation_models.py").read_text(
        encoding="utf-8"
    )
    assert (
        "from .design_lint_connectivity_snapshot_models import DesignLintConnectivitySnapshot"
        in report_source
    )
    assert "from .design_lint_connectivity_snapshot_models import (" in reconciliation_source
    assert "DesignLintConnectivityChange" in reconciliation_source
    assert design_lint_connectivity_snapshot_models.NativePinMetadata.__module__.endswith(
        "design_lint_connectivity_snapshot_models"
    )
    assert "DesignLintPinMetadataChange" in reconciliation_source


def test_report_validation_owners_stay_bounded_by_evidence_scope() -> None:
    owners = {
        "design_lint_report_evidence_validation.py": "validate_source_bound_evidence",
        "design_lint_report_peer_coverage_validation.py": "validate_peer_coverage",
        "design_lint_report_connector_coverage_validation.py": (
            "validate_connector_peer_pin_coverage"
        ),
        "design_lint_report_catalog_validation.py": "validate_catalogued_findings",
    }
    for name, function_name in owners.items():
        path = TOOLING / "hwrepo" / name
        assert path.is_file(), f"Missing report validation owner: {name}"
        source = path.read_text(encoding="utf-8")
        assert len(source.splitlines()) < 500
        tree = ast.parse(source, filename=path.as_posix())
        assert any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
            for node in tree.body
        ), f"{function_name} must remain owned by {name}"

    report_source = OWNER.read_text(encoding="utf-8")
    for owner in owners:
        assert f"from .{owner.removesuffix('.py')} import" in report_source
