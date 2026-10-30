"""Compare dated saved supplier offers for a source-bound reviewed BOM."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.supplier_analysis import compare_supplier_snapshots


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True)
    parser.add_argument("--parts-receipt", type=Path, required=True)
    parser.add_argument("--before", type=Path, required=True, help="Saved sourcing snapshot JSON")
    parser.add_argument("--after", type=Path, required=True, help="Saved sourcing snapshot JSON")
    parser.add_argument("--as-of", required=True, help="Comparison date, YYYY-MM-DD")
    parser.add_argument("--max-age-days", type=int, required=True)
    parser.add_argument("--output", type=Path, help="Fresh ignored build/ directory")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = compare_supplier_snapshots(
            args.root,
            args.project,
            args.parts_receipt,
            args.before,
            args.after,
            date.fromisoformat(args.as_of),
            args.max_age_days,
            args.output,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"Supplier analysis could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"Supplier analysis: {report.project_id}")
        print(f"  Offers: {len(report.offers)}; currencies: {', '.join(report.currencies)}")
        print(f"Open: {report.output_directory}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
