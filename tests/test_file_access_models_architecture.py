"""File access records have one owner and keep their established imports."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import file_access_models, models

pytestmark = pytest.mark.architecture

NAMES = ("McpFileContent", "McpEditPreview", "McpEditResult")
PACKAGE = Path(__file__).parents[1] / "kicad_tooling/hwrepo"


@pytest.mark.parametrize("name", NAMES)
def test_legacy_export_is_the_owner_and_json_schema_is_stable(name: str) -> None:
    owner = getattr(file_access_models, name)
    assert getattr(models, name) is owner
    schema = owner.model_json_schema()
    assert schema["title"] == name
    assert schema["properties"]["schema_version"]["const"] == "1"
    assert schema["properties"]["build_authorized"]["const"] is False


@pytest.mark.parametrize(
    ("name", "payload"),
    (
        (
            "McpFileContent",
            {
                "path": "docs/a.md",
                "sha256": "a" * 64,
                "size_bytes": 3,
                "content_kind": "text",
                "text": "abc",
                "offset": 0,
            },
        ),
        (
            "McpEditPreview",
            {
                "project_id": "board",
                "path": "docs/a.md",
                "before_sha256": "a" * 64,
                "after_sha256": "b" * 64,
                "diff": "-a\n+b\n",
                "validation": "TEXT_ONLY",
                "next_command": "verify",
            },
        ),
        (
            "McpEditResult",
            {
                "project_id": "board",
                "path": "docs/a.md",
                "before_sha256": "a" * 64,
                "after_sha256": "b" * 64,
                "readback_sha256": "b" * 64,
                "next_command": "verify",
            },
        ),
    ),
)
def test_legacy_json_round_trips_through_owner(name: str, payload: dict[str, object]) -> None:
    legacy = getattr(models, name).model_validate(payload)
    restored = getattr(file_access_models, name).model_validate_json(legacy.model_dump_json())
    assert restored == legacy


def test_services_import_file_contracts_from_owner_without_registry_cycle() -> None:
    owner = ast.parse((PACKAGE / "file_access_models.py").read_text(encoding="utf-8"))
    assert all(
        node.module != "models" for node in ast.walk(owner) if isinstance(node, ast.ImportFrom)
    )
    for name in (
        "bounded_file_content.py",
        "project_source_access.py",
        "mcp_files.py",
        "mcp_server.py",
    ):
        tree = ast.parse((PACKAGE / name).read_text(encoding="utf-8"))
        assert any(
            isinstance(node, ast.ImportFrom) and node.module == "file_access_models"
            for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, ast.ImportFrom)
            and node.module == "models"
            and any(alias.name in NAMES for alias in node.names)
            for node in ast.walk(tree)
        )
