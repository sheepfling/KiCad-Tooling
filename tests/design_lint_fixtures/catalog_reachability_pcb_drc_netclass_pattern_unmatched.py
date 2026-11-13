"""Source-bound catalog reachability for unmatched PCB netclass patterns."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_netclass_pattern_review import (
    source_bound_pcb_netclass_pattern_candidates,
)


def pcb_drc_netclass_pattern_unmatched_rule_ids() -> frozenset[str]:
    """Reach the rule using a tooling-owned unmatched-pattern pair."""
    repository = Path(__file__).resolve().parents[2]
    fixture_root = repository / "tests/fixtures/design_lint/pcb-drc-duplicate-net-settings"
    with tempfile.TemporaryDirectory(prefix="kicad-netclass-pattern-reachability-") as temporary:
        root = Path(temporary)
        project_relative = "projects/controller.kicad_pro"
        board_relative = "projects/controller.kicad_pcb"
        project = root / project_relative
        board = root / board_relative
        project.parent.mkdir(parents=True)
        shutil.copyfile(fixture_root / "fault-unmatched.kicad_pro", project)
        shutil.copyfile(fixture_root / "board.kicad_pcb", board)
        config = cast(
            ProjectConfig,
            SimpleNamespace(
                kind=ProjectKind.PCB,
                project=project_relative,
                kicad_version="10.0.8",
            ),
        )
        candidates = source_bound_pcb_netclass_pattern_candidates(
            root,
            config,
            {project_relative: digest(project), board_relative: digest(board)},
        )
    return frozenset(item.rule_id for item in candidates)
