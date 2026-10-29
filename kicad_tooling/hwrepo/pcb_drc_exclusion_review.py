"""Source-bound review candidates for persisted PCB DRC exclusions."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path

from .contracts import repo_path
from .design_lint_types import Candidate
from .evidence import digest
from .pcb_drc_project_settings import pcb_drc_exclusions
from .project_models import (
    ProjectConfig,
    ProjectKind,
)

_SUPPORTED_KICAD_VERSION = re.compile(r"10\.0\.\d+\Z")


def source_bound_pcb_drc_exclusion_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: Mapping[str, str],
) -> tuple[Candidate, ...]:
    """Prompt to recheck each saved per-violation DRC exclusion in KiCad 10.0."""
    if config.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        return ()
    if _SUPPORTED_KICAD_VERSION.fullmatch(config.kicad_version) is None:
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
        exclusions = pcb_drc_exclusions(document)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(f"{relative}: could not read supported PCB DRC exclusions: {exc}") from exc
    if digest(settings_file) != expected_hash:
        raise ValueError("KiCad project settings changed during design-lint inspection")

    candidates: list[Candidate] = []
    for exclusion in exclusions:
        marker_sha256 = hashlib.sha256(exclusion.marker.encode("utf-8")).hexdigest()
        drc_rule_key = exclusion.marker.partition("|")[0]
        comment_state = (
            "with no explanatory comment"
            if not exclusion.comment.strip()
            else "with a saved comment"
        )
        candidates.append(
            Candidate(
                rule_id="pcb.drc_exclusion_present",
                subject=f"{relative}#board/design_settings/drc_exclusions/{marker_sha256}",
                message=(
                    f"A saved per-violation DRC exclusion targets {drc_rule_key!r} {comment_state}; "
                    "confirm the individual violation and its exception are still intentional."
                ),
                evidence={
                    "source_path": (relative,),
                    "source_sha256": (expected_hash,),
                    "kicad_version": (config.kicad_version,),
                    "drc_rule_key": (drc_rule_key,),
                    "exclusion_marker_sha256": (marker_sha256,),
                    "serialized_marker": (exclusion.marker,),
                    "exclusion_comment": (exclusion.comment,),
                },
            )
        )
    return tuple(candidates)
