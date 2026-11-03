"""Compare one AC measurement in two saved electrical analysis receipts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.electrical_ac_comparison import compare_ac_runs
from .hwrepo.layout import default_project_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True)
    parser.add_argument("--baseline", required=True, type=Path, help="Saved electrical receipt")
    parser.add_argument("--candidate", required=True, type=Path, help="Saved electrical receipt")
    parser.add_argument("--case", required=True, dest="case_id", help="Exact AC case ID")
    parser.add_argument("--measure", required=True, dest="measure_id", help="Exact measurement ID")
    parser.add_argument("--output", type=Path, help="Fresh directory under build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = compare_ac_runs(
            args.root,
            args.project,
            args.baseline,
            args.candidate,
            args.case_id,
            args.measure_id,
            args.output,
        )
    except (OSError, ValueError) as exc:
        print(f"AC comparison could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"AC comparison: {report.status}")
        print(f"Viewer: {report.output_directory}/index.html")
        print(f"Frequency overlap: {report.overlap}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
