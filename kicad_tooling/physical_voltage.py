"""Review a saved voltage series against project-authored context and limits."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.physical_voltage import build_physical_voltage_review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True, help="Exact project ID")
    parser.add_argument("--measured-receipt", type=Path, required=True)
    parser.add_argument(
        "--capture", type=Path, required=True, help="Project-owned capture context JSON"
    )
    parser.add_argument("--requirement", type=Path, help="Project-owned voltage requirement JSON")
    parser.add_argument("--output", type=Path, help="Fresh ignored build/ output directory")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = build_physical_voltage_review(
            args.root,
            args.project,
            args.measured_receipt,
            args.capture,
            args.requirement,
            args.output,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"Physical voltage review could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"Voltage review: {report.status}")
        print(f"  Samples: {report.samples}; out of limit: {report.violation_count}")
        print(f"  Requirement: {report.requirement_state}")
        print(f"Open: {report.output_directory}/index.html")
    return 1 if report.status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
