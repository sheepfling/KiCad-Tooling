"""Compare two saved named KiCad schematic and PCB populations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.board_variant_compare import compare_board_variants
from .hwrepo.layout import default_project_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True)
    parser.add_argument("--findings-view", type=Path, required=True)
    parser.add_argument("--before-variant", required=True)
    parser.add_argument("--after-variant", required=True)
    parser.add_argument("--output", type=Path, help="Fresh ignored build/ directory")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = compare_board_variants(
            args.root,
            args.project,
            args.findings_view,
            args.before_variant,
            args.after_variant,
            args.output,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"Board variant comparison could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        changed = sum(item.change != "UNCHANGED" for item in report.references)
        print(
            f"Board variants: {report.before.name} → {report.after.name}; {changed} changed references"
        )
        print(f"Open: {report.output_directory}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
