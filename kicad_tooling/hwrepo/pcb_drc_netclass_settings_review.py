"""Collect source-bound reviews for PCB netclass settings."""

from __future__ import annotations

from pathlib import Path

from .design_lint_types import Candidate
from .pcb_drc_malformed_netclass_assignment_review import (
    source_bound_pcb_malformed_netclass_assignment_candidates,
)
from .pcb_drc_malformed_netclass_inventory_review import (
    source_bound_pcb_malformed_netclass_inventory_candidates,
)
from .pcb_drc_malformed_netclass_numeric_constraints_review import (
    source_bound_pcb_malformed_netclass_numeric_constraint_candidates,
)
from .pcb_drc_netclass_conflict_review import source_bound_pcb_netclass_conflict_candidates
from .pcb_drc_netclass_pattern_review import source_bound_pcb_netclass_pattern_candidates
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
    """Run source-matched duplicate, malformed, and unresolved setting reviews."""
    return (
        *source_bound_pcb_netclass_conflict_candidates(root, config, source_hashes),
        *source_bound_pcb_malformed_netclass_assignment_candidates(
            root,
            config,
            source_hashes,
        ),
        *source_bound_pcb_malformed_netclass_inventory_candidates(
            root,
            config,
            source_hashes,
        ),
        *source_bound_pcb_malformed_netclass_numeric_constraint_candidates(
            root,
            config,
            source_hashes,
        ),
        *source_bound_pcb_unresolved_netclass_assignment_candidates(
            root,
            config,
            source_hashes,
        ),
        *source_bound_pcb_netclass_pattern_candidates(root, config, source_hashes),
    )
