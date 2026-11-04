"""Run actual KiCad validation through the shared native-project service."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.native_project_check import (
    run_native_project_check,
    selected_projects,
)
from .hwrepo.native_project_check_models import CheckAllSummary, NativeProjectCheckRequest
from .hwrepo.selection import ProjectSelector, resolve_project_ids

__all__ = ["check_all", "main", "run_native_project_check", "selected_projects"]


def check_all(
    root: Path, output: Path, cli: str, requested: Sequence[str] | None = None
) -> CheckAllSummary:
    """Compatibility adapter for the former positional check API."""
    return run_native_project_check(
        root,
        NativeProjectCheckRequest(
            output=output,
            cli=cli,
            project_ids=None if requested is None else tuple(requested),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
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
    result = run_native_project_check(
        args.root,
        NativeProjectCheckRequest(
            output=args.output.resolve(),
            cli=args.cli,
            project_ids=None if args.all or selected is None else selected,
        ),
    )
    print(result.model_dump_json(indent=2))
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
