"""Source-bound catalog reachability for repeated schematic ERC settings."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_erc_duplicate_severity_key_review import (
    source_bound_schematic_erc_duplicate_severity_key_candidates,
)


def schematic_erc_duplicate_severity_rule_ids() -> frozenset[str]:
    """Reach the repeated-key rule through its tooling-owned source fixture."""
    repository = Path(__file__).resolve().parents[2]
    relative = (
        "tests/fixtures/design_lint/schematic-erc-duplicate-severity/fault-ignore-last.kicad_pro"
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
    candidates = source_bound_schematic_erc_duplicate_severity_key_candidates(
        repository,
        config,
        {relative: digest(settings)},
    )
    return frozenset(item.rule_id for item in candidates)
