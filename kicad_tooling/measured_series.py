"""Import a project-owned CSV into a retained measured time-series plot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.measured_series import import_measured_series


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True, help="Exact project ID")
    parser.add_argument("--source", type=Path, required=True, help="Project-owned CSV path")
    parser.add_argument("--time-column", required=True, help="Exact CSV header")
    parser.add_argument("--time-unit", choices=("s", "ms", "us", "ns", "iso8601"), required=True)
    parser.add_argument(
        "--channel", action="append", required=True, help="Repeat COLUMN=UNIT, up to eight"
    )
    parser.add_argument("--output", type=Path, help="Fresh directory under ignored build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = import_measured_series(
            args.root,
            args.project,
            args.source,
            args.time_column,
            args.time_unit,
            tuple(args.channel),
            args.output,
        )
    except (OSError, ValueError) as exc:
        print(f"Measured series import could not start: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(
            f"Measured series: {report.status}\nReceipt: {report.output_directory}\nSamples: {report.samples}"
        )
        for error in report.errors:
            print(f"  {error}")
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
