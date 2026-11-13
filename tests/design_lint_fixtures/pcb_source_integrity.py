"""Source-bound PCB object identity catalog reachability fixture."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_footprint_path_integrity import (
    pcb_footprint_path_trailing_separator_candidates,
)
from kicad_tooling.hwrepo.pcb_object_uuid_integrity import (
    duplicate_pcb_object_uuid_candidates,
)


def pcb_source_integrity_rule_ids() -> frozenset[str]:
    """Reach active PCB source-identity rules using tooling-owned fixtures."""
    repository = Path(__file__).resolve().parents[2]
    relative = "tests/fixtures/design_lint/pcb-duplicate-object-uuid/fault.kicad_pcb"
    source = repository / relative
    project = relative.removesuffix(".kicad_pcb") + ".kicad_pro"
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=project, kicad_version="10.0.5"),
    )
    candidates = list(
        duplicate_pcb_object_uuid_candidates(
            repository,
            config,
            {relative: digest(source)},
        )
    )
    path_relative = (
        "tests/fixtures/design_lint/pcb-footprint-path-trailing-separator/fault.kicad_pcb"
    )
    path_source = repository / path_relative
    path_project = path_relative.removesuffix(".kicad_pcb") + ".kicad_pro"
    path_config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=path_project, kicad_version="10.0.5"),
    )
    candidates.extend(
        pcb_footprint_path_trailing_separator_candidates(
            repository,
            path_config,
            {path_relative: digest(path_source)},
        )
    )
    return frozenset(candidate.rule_id for candidate in candidates)
