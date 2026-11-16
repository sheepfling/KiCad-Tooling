"""Coordinate source-bound schematic lint checks by their owning modules."""

from __future__ import annotations

from pathlib import Path

from .design_lint_types import Candidate
from .project_models import ProjectConfig
from .schematic_conflicting_placed_footprint import (
    source_bound_conflicting_placed_footprint_candidates,
)
from .schematic_conflicting_placed_value import (
    source_bound_conflicting_placed_value_candidates,
)
from .schematic_erc_source_candidates import source_bound_schematic_erc_candidates
from .schematic_reserved_dnp_property import (
    source_bound_reserved_dnp_property_candidates,
)
from .schematic_source_integrity import (
    duplicate_embedded_library_symbol_candidates,
    duplicate_schematic_object_uuid_candidates,
    embedded_symbol_pin_number_mismatch_candidates,
    missing_embedded_library_symbol_candidates,
)
from .source_state_models import SourceHashInventory


def collect_schematic_source_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Collect schematic source findings without implementing their predicates."""
    return (
        *source_bound_schematic_erc_candidates(root, config, source_hashes),
        *source_bound_conflicting_placed_value_candidates(root, config, source_hashes),
        *source_bound_conflicting_placed_footprint_candidates(root, config, source_hashes),
        *source_bound_reserved_dnp_property_candidates(root, config, source_hashes),
        *missing_embedded_library_symbol_candidates(root, config, source_hashes),
        *duplicate_embedded_library_symbol_candidates(root, config, source_hashes),
        *duplicate_schematic_object_uuid_candidates(root, config, source_hashes),
        *embedded_symbol_pin_number_mismatch_candidates(root, config, source_hashes),
    )
