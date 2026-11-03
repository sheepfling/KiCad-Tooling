"""Compare two explicitly retained product views across source revisions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.product_revision_bom import compare_product_revisions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Fresh ignored build/ directory")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = compare_product_revisions(args.root, args.baseline, args.candidate, args.output)
    except (OSError, ValueError, TypeError) as exc:
        print(f"Product revision BOM could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"Product revision BOM: {report.product_id} ({report.status})")
        print(f"Open: {report.output_directory}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
