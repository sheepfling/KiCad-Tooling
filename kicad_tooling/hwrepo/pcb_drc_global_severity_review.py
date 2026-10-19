"""Source-bound review candidates for suppressed core native PCB DRC checks."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .contracts import repo_path
from .design_lint_types import Candidate
from .evidence import digest
from .models import ProjectConfig, ProjectKind
from .pcb_drc_project_settings import configured_core_drc_check_severities


def _source_bound_core_drc_settings(
    root: Path,
    config: ProjectConfig,
    source_hashes: Mapping[str, str],
) -> tuple[str, str, tuple[tuple[str, str], ...]] | None:
    if config.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        return None
    if not config.kicad_version.startswith("10."):
        return None

    root = root.resolve()
    relative = str(config.project)
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
        severities = configured_core_drc_check_severities(document)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported PCB DRC severity settings: {exc}"
        ) from exc
    if digest(settings_file) != expected_hash:
        raise ValueError("KiCad project settings changed during design-lint inspection")
    return relative, expected_hash, severities


def ignored_core_native_drc_check_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: Mapping[str, str],
) -> tuple[Candidate, ...]:
    """Prompt when source-bound KiCad 10 settings suppress a core PCB DRC check."""
    settings = _source_bound_core_drc_settings(root, config, source_hashes)
    if settings is None:
        return ()
    relative, expected_hash, severities = settings

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
        for check_id, severity in severities
        if severity == "ignore"
    )


def warning_core_native_drc_check_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: Mapping[str, str],
) -> tuple[Candidate, ...]:
    """Review Error-default core PCB checks explicitly downgraded to Warning."""
    settings = _source_bound_core_drc_settings(root, config, source_hashes)
    if settings is None:
        return ()
    relative, expected_hash, severities = settings
    return tuple(
        Candidate(
            rule_id="pcb.core_drc_check_warning",
            subject=f"{relative}#board/design_settings/rule_severities/{check_id}",
            message=(
                f"Error-default core DRC check {check_id!r} is configured as Warning; "
                "confirm that lowering its severity is intentional."
            ),
            evidence={
                "source_path": (relative,),
                "source_sha256": (expected_hash,),
                "kicad_version": (config.kicad_version,),
                "check_id": (check_id,),
                "configured_severity": (severity,),
            },
        )
        for check_id, severity in severities
        if severity == "warning"
    )
