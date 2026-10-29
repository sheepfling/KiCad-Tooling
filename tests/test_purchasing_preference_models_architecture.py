"""Purchasing preference contracts retain their registry and JSON compatibility."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo import models, purchasing_preference_models

pytestmark = pytest.mark.architecture

NAMES = ("PurchasingSchemaModel", "PurchasingPreferences", "McpPurchasingPreferencesResult")
PACKAGE = Path(__file__).parents[1] / "kicad_tooling/hwrepo"


def test_registry_exports_are_identical_and_legacy_json_round_trips() -> None:
    for name in NAMES:
        assert getattr(models, name) is getattr(purchasing_preference_models, name)
    original = models.McpPurchasingPreferencesResult.model_validate(
        {
            "status": "UPDATED",
            "project_id": "board",
            "path": "docs/purchasing.json",
            "before_sha256": "a" * 64,
            "after_sha256": "b" * 64,
            "readback_sha256": "b" * 64,
            "preferences": {"boards": 2, "digikey_skus": {"R1": "123-ABC"}},
        }
    )
    restored = purchasing_preference_models.McpPurchasingPreferencesResult.model_validate_json(
        original.model_dump_json()
    )
    assert restored == original
    assert not restored.purchase_authorized and not restored.build_authorized
    with pytest.raises(ValidationError):
        purchasing_preference_models.PurchasingPreferences.model_validate({"schema_version": "2"})
    with pytest.raises(ValidationError):
        purchasing_preference_models.PurchasingPreferences.model_validate(
            {"digikey_skus": {"R1": " padded "}}
        )


def test_preference_services_use_the_owner_without_registry_cycles() -> None:
    owner = ast.parse((PACKAGE / "purchasing_preference_models.py").read_text(encoding="utf-8"))
    assert all(
        node.module != "models" for node in ast.walk(owner) if isinstance(node, ast.ImportFrom)
    )
    for name in (
        "project_source_access.py",
        "mcp_server.py",
        "part_picker.py",
        "purchasing.py",
        "parts_assistant.py",
        "parts_workflow.py",
        "purchasing_preferences.py",
    ):
        tree = ast.parse((PACKAGE / name).read_text(encoding="utf-8"))
        assert any(
            isinstance(node, ast.ImportFrom) and node.module == "purchasing_preference_models"
            for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, ast.ImportFrom)
            and node.module == "models"
            and any(alias.name in NAMES for alias in node.names)
            for node in ast.walk(tree)
        )
