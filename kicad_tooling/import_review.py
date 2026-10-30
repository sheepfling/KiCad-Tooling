"""Create an offline onboarding review for a selected project source."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.import_review import build_import_review
from .hwrepo.layout import default_project_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--source", type=Path, required=True, help="Selected source file")
    parser.add_argument("--project-id", required=True, help="Proposed project ID")
    parser.add_argument("--toolchain", required=True, help="Declared toolchain ID")
    parser.add_argument("--output", type=Path, help="Fresh ignored build/ directory")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = build_import_review(
            args.root, args.source, args.project_id, args.toolchain, args.output
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"Import review could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"Import review: {report.project_id} · {report.status}")
        print(f"  {len(report.files)} source rows; {len(report.dependencies)} CAD references")
        print(f"Open: {report.output_directory}/index.html")
    return 0 if report.status == "PREVIEW_CLEAR" else 1


if __name__ == "__main__":
    raise SystemExit(main())
