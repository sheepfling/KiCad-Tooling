"""Compare two saved measured traces with explicit time alignment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.measured_comparison import compare_measured_series


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--alignment", choices=("absolute", "elapsed"), required=True)
    parser.add_argument("--output", type=Path, help="Fresh directory under ignored build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = compare_measured_series(
            args.root,
            args.project,
            args.baseline,
            args.candidate,
            args.channel,
            args.alignment,
            args.output,
        )
    except (OSError, ValueError) as exc:
        print(f"Measured comparison could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"Measured comparison: {report.source_status}; {report.overlap}")
        print(f"Receipt: {report.output_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
