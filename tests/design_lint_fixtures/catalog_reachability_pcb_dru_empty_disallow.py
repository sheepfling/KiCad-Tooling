"""Synthetic catalog reachability for empty custom DRC disallow clauses."""

from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.pcb_dru_empty_disallow_review import (
    empty_custom_drc_disallow_candidates,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind


def pcb_dru_empty_disallow_rule_ids() -> frozenset[str]:
    """Reach the rule using a tooling-owned empty disallow clause."""
    repository = Path(__file__).resolve().parents[2]
    fixture = (
        repository
        / "tests/fixtures/design_lint/pcb-dru-empty-disallow/fault-empty-object-list.kicad_dru"
    )
    relative = "projects/controller.kicad_dru"
    with TemporaryDirectory(prefix="pcb-dru-empty-disallow-reachability-") as temporary:
        root = Path(temporary)
        (root / "projects").mkdir()
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
        candidates = empty_custom_drc_disallow_candidates(root, config, {relative: digest(rules)})
        return frozenset(item.rule_id for item in candidates)
