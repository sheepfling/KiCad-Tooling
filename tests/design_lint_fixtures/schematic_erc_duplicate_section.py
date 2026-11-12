"""Source-bound catalog reachability for repeated schematic ERC sections."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_erc_duplicate_section_review import (
    source_bound_schematic_erc_duplicate_section_candidates,
)


def schematic_erc_duplicate_section_rule_ids() -> frozenset[str]:
    """Reach the rule using its tooling-owned repeated-section settings."""
    repository = Path(__file__).resolve().parents[2]
    relative = (
        "tests/fixtures/design_lint/schematic-erc-duplicate-section/fault-warning-ignore.kicad_pro"
    )
    settings = repository / relative
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=relative,
            kicad_version="10.0.8",
        ),
    )
    candidates = source_bound_schematic_erc_duplicate_section_candidates(
        repository,
        config,
        {relative: digest(settings)},
    )
    return frozenset(item.rule_id for item in candidates)
