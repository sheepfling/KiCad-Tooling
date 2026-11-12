"""Collect source-bound schematic ERC settings review candidates."""

from __future__ import annotations

from pathlib import Path

from .design_lint_types import Candidate
from .project_models import ProjectConfig
from .schematic_erc_catalog_coverage import (
    source_bound_schematic_erc_catalog_coverage_candidates,
)
from .schematic_erc_duplicate_severity_key_review import (
    source_bound_schematic_erc_duplicate_severity_key_candidates,
)
from .schematic_erc_exclusion_review import source_bound_schematic_erc_exclusion_candidates
from .schematic_erc_global_severity_review import (
    source_bound_schematic_erc_ignored_rule_candidates,
)
from .schematic_erc_invalid_severity_value_review import (
    source_bound_schematic_erc_invalid_severity_value_candidates,
)
from .schematic_erc_nonstring_severity_value_review import (
    source_bound_schematic_erc_nonstring_severity_value_candidates,
)
from .schematic_erc_unknown_rule_key_review import (
    source_bound_schematic_erc_unknown_rule_key_candidates,
)
from .schematic_erc_warning_downgrade import (
    source_bound_schematic_erc_warning_downgrade_candidates,
)
from .source_state_models import SourceHashInventory


def source_bound_schematic_erc_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Collect schematic ERC source-setting reviews in stable rule order."""
    return (
        *source_bound_schematic_erc_catalog_coverage_candidates(root, config, source_hashes),
        *source_bound_schematic_erc_exclusion_candidates(root, config, source_hashes),
        *source_bound_schematic_erc_ignored_rule_candidates(root, config, source_hashes),
        *source_bound_schematic_erc_unknown_rule_key_candidates(root, config, source_hashes),
        *source_bound_schematic_erc_invalid_severity_value_candidates(root, config, source_hashes),
        *source_bound_schematic_erc_duplicate_severity_key_candidates(root, config, source_hashes),
        *source_bound_schematic_erc_nonstring_severity_value_candidates(
            root, config, source_hashes
        ),
        *source_bound_schematic_erc_warning_downgrade_candidates(root, config, source_hashes),
    )
