"""Read saved PCB project settings only from source-hashed project inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .contracts import repo_path
from .evidence import digest
from .source_state_models import SourceHashInventory


@dataclass(frozen=True, slots=True)
class SourceBoundPcbProjectSettings:
    """The exact project-settings text captured from a source inventory."""

    source_path: str
    source_sha256: str
    document: str


def read_source_bound_pcb_project_settings(
    root: Path,
    relative: str,
    source_hashes: SourceHashInventory,
) -> SourceBoundPcbProjectSettings | None:
    """Read settings only when the file is declared and unchanged in source hashes."""
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
    return SourceBoundPcbProjectSettings(relative, expected_hash, document)


def verify_source_bound_pcb_project_settings_unchanged(
    root: Path,
    source: SourceBoundPcbProjectSettings,
) -> None:
    """Confirm settings still match the captured source identity after analysis."""
    settings_file = repo_path(root.resolve(), source.source_path)
    if not settings_file.is_file() or digest(settings_file) != source.source_sha256:
        raise ValueError("KiCad project settings changed during design-lint inspection")
