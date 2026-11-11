"""Read KiCad schematic project settings from hash-bound source inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .contracts import repo_path
from .evidence import digest
from .source_state_models import SourceHashInventory


@dataclass(frozen=True, slots=True)
class SourceBoundSchematicErcSettings:
    """The saved project-settings text bound to one source inventory digest."""

    source_path: str
    source_sha256: str
    document: str


def read_source_bound_schematic_erc_settings(
    root: Path,
    relative: str,
    source_hashes: SourceHashInventory,
) -> SourceBoundSchematicErcSettings | None:
    """Read settings only when the file is included and unchanged in source hashes."""
    root = root.resolve()
    settings_file = repo_path(root, relative)
    expected_hash = source_hashes.get(relative)
    if not settings_file.exists():
        if expected_hash is not None:
            raise ValueError("Source-bound KiCad project settings disappeared during inspection")
        return None
    if not settings_file.is_file():
        raise ValueError("KiCad project settings path is not a regular file")
    if expected_hash is None:
        raise ValueError("KiCad project settings are outside source-bound project inputs")
    if digest(settings_file) != expected_hash:
        raise ValueError("KiCad project settings differ from source-bound project inputs")
    try:
        document = settings_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"Could not read KiCad project settings: {exc}") from exc
    if digest(settings_file) != expected_hash:
        raise ValueError("KiCad project settings changed during design-lint inspection")
    return SourceBoundSchematicErcSettings(relative, expected_hash, document)


def verify_source_bound_schematic_erc_settings_unchanged(
    root: Path,
    source: SourceBoundSchematicErcSettings,
) -> None:
    """Reject project-setting edits made after their source-bound read."""
    if digest(repo_path(root.resolve(), source.source_path)) != source.source_sha256:
        raise ValueError("KiCad project settings changed during design-lint inspection")
