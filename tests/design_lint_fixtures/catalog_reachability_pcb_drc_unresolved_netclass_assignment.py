"""Source-bound catalog reachability for unresolved PCB netclass assignments."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_unresolved_netclass_assignment_review import (
    source_bound_pcb_unresolved_netclass_assignment_candidates,
)


def pcb_drc_unresolved_netclass_assignment_rule_ids() -> frozenset[str]:
    """Reach the rule using the tooling-owned undeclared-class fixture."""
    repository = Path(__file__).resolve().parents[2]
    relative = (
        "tests/fixtures/design_lint/pcb-drc-duplicate-net-settings/"
        "fault-netclass-assignment-undeclared.kicad_pro"
    )
    settings = repository / relative
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=relative, kicad_version="10.0.8"),
    )
    candidates = source_bound_pcb_unresolved_netclass_assignment_candidates(
        repository,
        config,
        {relative: digest(settings)},
    )
    return frozenset(item.rule_id for item in candidates)
