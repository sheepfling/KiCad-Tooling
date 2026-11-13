"""Synthetic source-bound reachability for contradictory custom DRC bounds."""

from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.pcb_dru_contradictory_bounds_review import (
    contradictory_custom_drc_constraint_candidates,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind


def pcb_dru_contradictory_bounds_rule_ids() -> frozenset[str]:
    """Reach the source rule with the tooling-owned contradiction fixture."""
    repository = Path(__file__).resolve().parents[2]
    fixture = (
        repository
        / "tests/fixtures/design_lint/pcb-dru-contradictory-bounds/fault-min-exceeds-max.kicad_dru"
    )
    relative = "projects/controller.kicad_dru"
    with TemporaryDirectory(prefix="pcb-dru-contradictory-bounds-reachability-") as temporary:
        root = Path(temporary)
        project_dir = root / "projects"
        project_dir.mkdir()
        (root / "projects/controller.kicad_pro").write_text("{}", encoding="utf-8")
        rules = root / relative
        shutil.copyfile(fixture, rules)
        config = cast(
            ProjectConfig,
            SimpleNamespace(
                kind=ProjectKind.PCB,
                project="projects/controller.kicad_pro",
                kicad_version="10.0.8",
            ),
        )
        candidates = contradictory_custom_drc_constraint_candidates(
            root,
            config,
            {relative: digest(rules)},
        )
        return frozenset(item.rule_id for item in candidates)
