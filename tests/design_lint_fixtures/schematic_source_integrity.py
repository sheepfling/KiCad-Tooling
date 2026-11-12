"""Source-bound schematic integrity catalog reachability fixtures."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_source_integrity import (
    missing_embedded_library_symbol_candidates,
)


def schematic_source_integrity_rule_ids() -> frozenset[str]:
    """Reach schematic source-integrity rules from stored tooling fixtures."""
    repository = Path(__file__).resolve().parents[2]
    relative = "tests/fixtures/design_lint/missing-embedded-symbol-definition/fault.kicad_sch"
    source = repository / relative
    project = relative.removesuffix(".kicad_sch") + ".kicad_pro"
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=project,
            kicad_version="10.0.5",
        ),
    )
    candidates = missing_embedded_library_symbol_candidates(
        repository,
        config,
        {relative: digest(source)},
    )
    return frozenset(item.rule_id for item in candidates)
