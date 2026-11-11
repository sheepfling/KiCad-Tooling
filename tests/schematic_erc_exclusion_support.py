"""Synthetic KiCad project settings used by ERC exclusion regressions."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_erc_exclusion_review import (
    source_bound_schematic_erc_exclusion_candidates,
)

FIXTURES = Path(__file__).parent / "fixtures/design_lint/schematic-erc-exclusions"
PROJECT_RELATIVE = "projects/controller.kicad_pro"


def erc_exclusion_project(
    tmp_path: Path,
    fixture: str = "fault.kicad_pro",
    *,
    kicad_version: str = "10.0.5",
    kind: ProjectKind = ProjectKind.PCB,
) -> tuple[Path, Path, ProjectConfig, dict[str, str]]:
    """Copy one tooling-owned settings fixture and bind its source hash."""
    root = tmp_path / "repository"
    project = root / PROJECT_RELATIVE
    project.parent.mkdir(parents=True)
    project.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=kind, project=PROJECT_RELATIVE, kicad_version=kicad_version),
    )
    return root, project, config, {PROJECT_RELATIVE: digest(project)}


def source_bound_erc_exclusion_rule_ids() -> set[str]:
    """Return active rule IDs from the synthetic source-bound settings fault."""
    with TemporaryDirectory() as temporary_directory:
        root, _, config, source_hashes = erc_exclusion_project(Path(temporary_directory))
        return {
            item.rule_id
            for item in source_bound_schematic_erc_exclusion_candidates(root, config, source_hashes)
        }
