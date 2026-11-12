"""Source-bound catalog reachability for duplicate PCB DRC severity keys."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_duplicate_severity_key_review import (
    source_bound_pcb_drc_duplicate_severity_key_candidates,
)


def pcb_drc_duplicate_severity_key_rule_ids() -> frozenset[str]:
    """Reach the duplicate-key rule through its tooling-owned synthetic settings."""
    repository = Path(__file__).resolve().parents[2]
    relative = (
        "tests/fixtures/design_lint/pcb-drc-duplicate-severity-key/fault-ignore-last.kicad_pro"
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
    candidates = source_bound_pcb_drc_duplicate_severity_key_candidates(
        repository,
        config,
        {relative: digest(settings)},
    )
    return frozenset(item.rule_id for item in candidates)
