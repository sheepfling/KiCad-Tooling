"""Source-bound catalog reachability for non-string schematic ERC values."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_erc_nonstring_severity_value_review import (
    source_bound_schematic_erc_nonstring_severity_value_candidates,
)


def schematic_erc_nonstring_severity_rule_ids() -> frozenset[str]:
    """Reach the new rule through its tooling-owned boolean fault setting."""
    repository = Path(__file__).resolve().parents[2]
    relative = "tests/fixtures/design_lint/schematic-erc-nonstring-severity/fault-boolean.kicad_pro"
    settings = repository / relative
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=relative,
            kicad_version="10.0.8",
        ),
    )
    candidates = source_bound_schematic_erc_nonstring_severity_value_candidates(
        repository,
        config,
        {relative: digest(settings)},
    )
    return frozenset(item.rule_id for item in candidates)
