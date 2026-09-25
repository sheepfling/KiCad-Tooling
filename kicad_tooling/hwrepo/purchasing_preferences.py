"""Shared, typed purchasing preference writes with optimistic concurrency guards."""
from __future__ import annotations

from pathlib import Path

from . import mcp_files, parts_workflow
from .contracts import parse_model_text, repo_path
from .models import McpPurchasingPreferencesResult, PurchasingPreferences
from .parts_workflow import selected_project


def save_parts_preferences(
    root: Path, project_id: str, preferences: PurchasingPreferences,
    expected_sha256: str | None = None,
) -> McpPurchasingPreferencesResult:
    """Save explicit preferences at the fixed authored path; updates need a current hash."""
    text = preferences.model_dump_json(indent=2) + "\n"
    if len(text) > mcp_files.MAX_CHUNK:
        raise ValueError("Preferences exceed the supported edit size")
    project = selected_project(root, project_id)
    relative = (Path(project.config).parent / "docs/purchasing.json").as_posix()
    path = repo_path(root, relative)
    before = None
    if path.exists():
        if expected_sha256 is None:
            raise ValueError("Existing preferences require expected_sha256 from read_project_file")
        previous = mcp_files.read_project_file(root, project_id, "docs/purchasing.json")
        if previous.text is None or previous.truncated:
            raise ValueError("Preferences exceed the supported edit size")
        if previous.sha256 != expected_sha256:
            raise ValueError("Source hash mismatch; read the current preferences and review again")
        before = previous.sha256
        if previous.text != text:
            mcp_files.apply_project_edit(
                root, project_id, "docs/purchasing.json", expected_sha256, previous.text, text,
            )
        status = "UPDATED"
    else:
        if expected_sha256 is not None:
            raise ValueError("Preferences no longer exist; review a new creation without a digest")
        parts_workflow.init_preferences(root, project_id, path, preferences)
        status = "CREATED"
    content = mcp_files.read_project_file(root, project_id, "docs/purchasing.json")
    if content.text is None or content.truncated:
        raise ValueError("Preferences readback exceeded the supported size")
    saved = parse_model_text(content.text, PurchasingPreferences)
    if saved != preferences:
        raise ValueError("Preferences changed during readback; reread before continuing")
    return McpPurchasingPreferencesResult(
        project_id=project_id, path=relative, status=status, before_sha256=before,
        after_sha256=content.sha256, readback_sha256=content.sha256, preferences=saved,
    )
