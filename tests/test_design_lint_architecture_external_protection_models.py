"""Keep external-protection requirements and coverage in their theme owner."""

from __future__ import annotations

import ast
from dataclasses import fields
from types import MappingProxyType
from typing import get_type_hints

import pytest

from kicad_tooling.hwrepo import external_protection_models
from kicad_tooling.hwrepo import models as shared_models
from kicad_tooling.hwrepo.external_protection import (
    ExternalProtectionCoverageRequest,
    ExternalProtectionCoverageResolution,
    resolve_external_protection_coverage,
)
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
    pytest.mark.evidence_lint,
]

EXTERNAL_PROTECTION_MODEL_NAMES = (
    "ExternalProtectionChannelRequirement",
    "ExternalProtectionInterfaceRequirement",
    "ExternalProtectionDeviceRequirement",
    "ExternalProtectionMap",
    "ExternalProtectionCoverageEntry",
    "ExternalProtectionCoverageReport",
)

EXPECTED_OWNER_IMPORTS = MappingProxyType(
    {
        "design_lint_candidate_aggregation.py": frozenset({"ExternalProtectionCoverageReport"}),
        "design_lint_connector_coverage.py": frozenset({"ExternalProtectionCoverageReport"}),
        "design_lint_evaluation_types.py": frozenset({"ExternalProtectionCoverageReport"}),
        "design_lint_evaluator.py": frozenset({"ExternalProtectionCoverageReport"}),
        "design_lint_protection_candidates.py": frozenset({"ExternalProtectionCoverageReport"}),
        "design_lint_protection_candidate_evidence.py": frozenset(
            {"ExternalProtectionCoverageEntry", "ExternalProtectionCoverageReport"}
        ),
        "external_protection.py": frozenset(
            {
                "ExternalProtectionCoverageEntry",
                "ExternalProtectionCoverageReport",
                "ExternalProtectionDeviceRequirement",
                "ExternalProtectionMap",
            }
        ),
    }
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


def test_external_protection_models_live_in_owner_and_registry_exports_keep_identity() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/external_protection_models.py"
    registry_path = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    registry_tree = ast.parse(registry_path.read_text(encoding="utf-8"))

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert set(EXTERNAL_PROTECTION_MODEL_NAMES) <= _top_level_definitions(owner_tree)
    registry_classes = {node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)}
    assert not (set(EXTERNAL_PROTECTION_MODEL_NAMES) & registry_classes)
    for name in EXTERNAL_PROTECTION_MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(external_protection_models, name)


def test_internal_external_protection_services_import_models_from_owner() -> None:
    package = REPO_ROOT / "kicad_tooling"
    model_names = set(EXTERNAL_PROTECTION_MODEL_NAMES)
    legacy_imports: list[str] = []

    for source in sorted(package.rglob("*.py")):
        if source.name == "models.py":
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        imported_from_owner: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            names = {alias.name for alias in node.names}
            if node.module == "external_protection_models":
                imported_from_owner.update(names)
            elif node.module == "models" or node.module.endswith(".models"):
                legacy_imports.extend(
                    f"{source.relative_to(REPO_ROOT).as_posix()}:{name}"
                    for name in names & model_names
                )
        expected = EXPECTED_OWNER_IMPORTS.get(source.name)
        if expected:
            assert expected <= imported_from_owner, (
                f"{source.relative_to(REPO_ROOT).as_posix()} must import theme-owned "
                f"models directly: missing {sorted(expected - imported_from_owner)}"
            )

    assert not legacy_imports, (
        "Internal external-protection services must not import these models from the "
        f"compatibility registry: {legacy_imports}"
    )


def test_evaluation_admits_coverage_through_the_theme_owned_source_request() -> None:
    assert {item.name for item in fields(ExternalProtectionCoverageRequest)} == {
        "coverage",
        "current_netlist_sha256",
    }
    assert {item.name for item in fields(ExternalProtectionCoverageResolution)} == {
        "coverage",
        "binding_issue",
    }
    assert get_type_hints(resolve_external_protection_coverage)["request"] is (
        ExternalProtectionCoverageRequest
    )
    assert get_type_hints(resolve_external_protection_coverage)["return"] is (
        ExternalProtectionCoverageResolution
    )

    preparation_path = REPO_ROOT / "kicad_tooling/hwrepo/design_lint_evaluation_preparation.py"
    preparation_tree = ast.parse(preparation_path.read_text(encoding="utf-8"))
    request_calls = [
        node
        for node in ast.walk(preparation_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ExternalProtectionCoverageRequest"
    ]
    resolution_calls = [
        node
        for node in ast.walk(preparation_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "resolve_external_protection_coverage"
    ]
    assert len(request_calls) == len(resolution_calls) == 1
    request_arguments = {
        keyword.arg: ast.unparse(keyword.value) for keyword in request_calls[0].keywords
    }
    assert request_arguments == {
        "coverage": "request.external_protection_coverage",
        "current_netlist_sha256": "coach.netlist_sha256",
    }
    assert len(resolution_calls[0].args) == 1
    assert resolution_calls[0].args[0] is request_calls[0]
