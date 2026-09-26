"""Emit one digest-pinned KiCad CI lane per declared project."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.discovery import load_config, load_registry
from .hwrepo.models import CiMatrix, MatrixEntry
from .lint_registry import lint


def build_matrix(root: Path, selected: tuple[str, ...] | None = None) -> CiMatrix:
    root = root.resolve()
    governance = lint(root, None if selected is None else list(selected))
    if governance.status != "PASS":
        raise ValueError(
            f"Refusing CI matrix for invalid registry: {governance.issues}"
        )
    registry = load_registry(root)
    include: list[MatrixEntry] = []
    selected_ids = None if selected is None else frozenset(selected)
    for project in registry.projects:
        if selected_ids is not None and project.id not in selected_ids:
            continue
        config = load_config(root, project.config)
        include.append(
            MatrixEntry(
                project=project.id,
                image=config.image,
                kicad_version=config.kicad_version,
                electrical=config.electrical is not None,
                fault_probes=(
                    project.id == "controller"
                    and project.project == "examples/projects/controller/kicad/controller.kicad_pro"
                ),
            )
        )
    return CiMatrix(include=tuple(include))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--project", action="append", dest="projects")
    parser.add_argument("--tag", action="append", dest="tags")
    parser.add_argument("--product", action="append", dest="products")
    parser.add_argument("--exclude-tag", action="append", dest="excluded_tags")
    args = parser.parse_args()
    from .hwrepo.selection import ProjectSelector, resolve_project_ids

    selector = ProjectSelector(
        project_ids=tuple(args.projects or ()),
        tags=tuple(args.tags or ()),
        excluded_tags=tuple(args.excluded_tags or ()),
        product_ids=tuple(args.products or ()),
    )
    try:
        selected = resolve_project_ids(args.root, selector) if selector.active else None
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(build_matrix(args.root, selected).model_dump_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
