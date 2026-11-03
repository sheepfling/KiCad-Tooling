"""Review a source-bound parts plan for one named native board variant."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.variant_parts_review import build_variant_parts_review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True)
    parser.add_argument("--parts-report", type=Path, required=True)
    parser.add_argument("--findings-view", type=Path, required=True)
    parser.add_argument("--assembly-variant", required=True)
    parser.add_argument("--output", type=Path, help="Fresh ignored build/ directory")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = build_variant_parts_review(
            args.root,
            args.project,
            args.parts_report,
            args.findings_view,
            args.assembly_variant,
            args.output,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"Variant parts review could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(
            f"Variant {report.assembly_variant}: {len(report.plan.lines)} part groups, "
            f"{len(report.unresolved)} unresolved references"
        )
        print(f"Open: {report.output_directory}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
