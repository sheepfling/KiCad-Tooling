"""Catalog-reachability probes for global schematic ERC severity review."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_erc_global_severity_review import (
    source_bound_schematic_erc_ignored_rule_candidates,
)


def schematic_erc_global_severity_rule_ids() -> frozenset[str]:
    """Reach the active global-ignore rule from its source-bound synthetic fixture."""
    repository = Path(__file__).resolve().parents[2]
    relative = "tests/fixtures/design_lint/schematic-erc-global-severity/fault.kicad_pro"
    settings = repository / relative
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=relative, kicad_version="10.0.5"),
    )
    candidates = source_bound_schematic_erc_ignored_rule_candidates(
        repository,
        config,
        {relative: digest(settings)},
    )
    return frozenset(candidate.rule_id for candidate in candidates)
