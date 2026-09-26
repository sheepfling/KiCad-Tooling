"""Run actual KiCad validation for one declared project or every declared project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.contracts import write_model
from .hwrepo.discovery import load_registry
from .hwrepo.models import (
    CheckAllSummary,
    ProjectCheckSummary,
    ProjectRecord,
)
from .hwrepo.product import check as check_product
from .hwrepo.repository import check_repository
from .lint_registry import lint
from .validate import validate


def selected_projects(root: Path, requested: list[str] | None) -> tuple[ProjectRecord, ...]:
    registry = load_registry(root)
    available = {project.id: project for project in registry.projects}
    identifiers = tuple(available) if requested is None else tuple(requested)
    unknown = [identifier for identifier in identifiers if identifier not in available]
    if unknown:
        raise ValueError(f"Unknown project ids: {unknown}")
    return tuple(available[identifier] for identifier in identifiers)


def check_all(
    root: Path, output: Path, cli: str, requested: list[str] | None = None
) -> CheckAllSummary:
    root = root.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite retained evidence: {output}")
    output.mkdir(parents=True)
    governance = lint(root, requested)
    selected = None if requested is None else tuple(requested)
    repository = check_repository(root, selected)
    product_policy = check_product(root, selected_project_ids=selected)
    rows: list[ProjectCheckSummary] = []
    if (
        governance.status == "PASS"
        and repository.status == "PASS"
        and product_policy.status == "PASS"
    ):
        for project in selected_projects(root, requested):
            report = validate(root, output / project.id, cli, Path(project.config))
            rows.append(
                ProjectCheckSummary(
                    id=project.id,
                    status=report.status,
                    summary=f"{project.id}/summary.json",
                )
            )
    result = CheckAllSummary(
        governance=governance,
        repository=repository,
        product_policy=product_policy,
        projects=tuple(rows),
        status=(
            "PASS"
            if governance.status == "PASS" and rows and all(row.status == "PASS" for row in rows)
            else "FAIL"
        ),
    )
    write_model(output / "summary.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--cli",
        default="kicad-cli",
        help="KiCad CLI command or path (relative paths use the caller's cwd)",
    )
    parser.add_argument("--project", action="append", dest="projects")
    parser.add_argument("--tag", action="append", dest="tags")
    parser.add_argument("--product", action="append", dest="products")
    parser.add_argument("--exclude-tag", action="append", dest="excluded_tags")
    parser.add_argument(
        "--all", action="store_true", help="Check every declared project (the default)."
    )
    args = parser.parse_args()
    from .hwrepo.selection import ProjectSelector, resolve_project_ids

    selector = ProjectSelector(
        project_ids=tuple(args.projects or ()),
        tags=tuple(args.tags or ()),
        excluded_tags=tuple(args.excluded_tags or ()),
        product_ids=tuple(args.products or ()),
    )
    if args.all and selector.active:
        parser.error("--all cannot be combined with project selectors")
    try:
        selected = resolve_project_ids(args.root, selector) if selector.active else None
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    result = check_all(
        args.root,
        args.output.resolve(),
        args.cli,
        None if args.all or selected is None else list(selected),
    )
    print(result.model_dump_json(indent=2))
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
