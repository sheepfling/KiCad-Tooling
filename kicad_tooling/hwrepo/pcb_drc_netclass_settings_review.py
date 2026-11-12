"""Collect source-bound reviews for PCB netclass settings."""

from __future__ import annotations

from pathlib import Path

from .design_lint_types import Candidate
from .pcb_drc_netclass_conflict_review import source_bound_pcb_netclass_conflict_candidates
from .pcb_drc_unresolved_netclass_assignment_review import (
    source_bound_pcb_unresolved_netclass_assignment_candidates,
)
from .project_models import ProjectConfig
from .source_state_models import SourceHashInventory


def source_bound_pcb_netclass_settings_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Run the source-matched duplicate and unresolved netclass setting reviews."""
    return (
        *source_bound_pcb_netclass_conflict_candidates(root, config, source_hashes),
        *source_bound_pcb_unresolved_netclass_assignment_candidates(
            root,
            config,
            source_hashes,
        ),
    )
