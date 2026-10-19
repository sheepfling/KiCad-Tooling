"""Source-bound review candidates for suppressed core native PCB DRC checks."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .contracts import repo_path
from .design_lint_types import Candidate
from .evidence import digest
from .models import ProjectConfig, ProjectKind
from .pcb_drc_project_settings import ignored_core_drc_check_ids


def ignored_core_native_drc_check_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: Mapping[str, str],
) -> tuple[Candidate, ...]:
    """Prompt when source-bound KiCad 10 settings suppress a core PCB DRC check."""
    if config.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        return ()
    if not config.kicad_version.startswith("10."):
        return ()

    root = root.resolve()
    relative = str(config.project)
    settings_file = repo_path(root, relative)
    expected_hash = source_hashes.get(relative)
    if not settings_file.exists():
        if expected_hash is not None:
            raise ValueError("Source-bound KiCad project settings disappeared during inspection")
        return ()
    if not settings_file.is_file():
        raise ValueError("KiCad project settings path is not a regular file")
    if expected_hash is None:
        raise ValueError("KiCad project settings are outside source-bound project inputs")
    if digest(settings_file) != expected_hash:
        raise ValueError("KiCad project settings differ from source-bound project inputs")

    try:
        document = settings_file.read_text(encoding="utf-8")
        ignored_checks = ignored_core_drc_check_ids(document)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported PCB DRC severity settings: {exc}"
        ) from exc
    if digest(settings_file) != expected_hash:
        raise ValueError("KiCad project settings changed during design-lint inspection")

    return tuple(
        Candidate(
            rule_id="pcb.core_drc_check_ignored",
            subject=f"{relative}#board/design_settings/rule_severities/{check_id}",
            message=(
                f"Core native DRC check {check_id!r} is configured as Ignore; "
                "confirm that suppressing this check is intentional."
            ),
            evidence={
                "source_path": (relative,),
                "source_sha256": (expected_hash,),
                "kicad_version": (config.kicad_version,),
                "check_id": (check_id,),
                "configured_severity": ("ignore",),
            },
        )
        for check_id in ignored_checks
    )
