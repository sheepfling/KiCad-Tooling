"""Command execution evidence has a durable model owner."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import command_evidence_models, models

pytestmark = pytest.mark.architecture

_REPOSITORY_ROOT = Path(__file__).parents[1]


def test_command_evidence_has_a_small_primitive_only_owner() -> None:
    path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/command_evidence_models.py"
    source = path.read_text(encoding="utf-8")
    imports = ast.walk(ast.parse(source))
    imported_modules = {
        node.module
        for node in imports
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module != "__future__"
    }

    assert len(source.splitlines()) < 500
    assert imported_modules == {"model_primitives"}


def test_internal_services_import_command_evidence_from_its_owner() -> None:
    directory = _REPOSITORY_ROOT / "kicad_tooling"
    compatibility_registry = directory / "hwrepo/models.py"
    violations: list[str] = []
    for path in directory.rglob("*.py"):
        if path == compatibility_registry:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module not in {
                "models",
                "kicad_tooling.hwrepo.models",
            }:
                continue
            if any(alias.name == "CommandEvidence" for alias in node.names):
                violations.append(f"{path.relative_to(_REPOSITORY_ROOT)}:{node.lineno}")

    assert not violations, (
        "Internal callers must import the command evidence owner directly: " + ", ".join(violations)
    )


def test_models_registry_preserves_command_evidence_identity_and_json() -> None:
    command = command_evidence_models.CommandEvidence(
        argv=("kicad-cli", "version"),
        started_utc="2026-10-29T00:00:00Z",
        returncode=0,
    )

    assert models.CommandEvidence is command_evidence_models.CommandEvidence
    assert models.CommandEvidence.model_validate_json(command.model_dump_json()) == command
    assert (
        models.CommandEvidence.model_json_schema()
        == command_evidence_models.CommandEvidence.model_json_schema()
    )
