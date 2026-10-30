"""Compare two retained source-bound parts BOM receipts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.bom_compare import compare_bom
from .hwrepo.layout import default_project_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True)
    parser.add_argument("--before", type=Path, required=True, help="Earlier parts report.json")
    parser.add_argument("--after", type=Path, required=True, help="Later parts report.json")
    parser.add_argument("--output", type=Path, help="Fresh directory under ignored build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = compare_bom(args.root, args.project, args.before, args.after, args.output)
    except (OSError, ValueError) as exc:
        print(f"BOM comparison could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        changed = sum(item.change != "UNCHANGED" for item in report.references)
        print(f"BOM comparison: {changed} changed references\nReceipt: {report.output_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
