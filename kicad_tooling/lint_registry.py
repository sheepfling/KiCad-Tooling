"""CLI compatibility surface for project governance lint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.contracts import write_model
from .hwrepo.governance_lint import lint
from .hwrepo.governance_records import (
    lint_governance_record,
    records_by_id,
    reviewed_value,
)
from .hwrepo.layout import default_project_root
from .hwrepo.selection import ProjectSelector, resolve_project_ids

__all__ = ["lint", "lint_governance_record", "main", "records_by_id", "reviewed_value"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", action="append", dest="projects")
    parser.add_argument("--tag", action="append", dest="tags")
    parser.add_argument("--product", action="append", dest="products")
    parser.add_argument("--exclude-tag", action="append", dest="excluded_tags")
    parser.add_argument(
        "--all", action="store_true", help="Lint every declared project (the default)."
    )
    parser.add_argument("--output", type=Path)
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
    result = lint(args.root, None if args.all else None if selected is None else list(selected))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_model(args.output, result)
    print(result.model_dump_json(indent=2))
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
