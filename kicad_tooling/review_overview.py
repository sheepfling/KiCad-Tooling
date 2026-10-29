"""Create an offline project overview from explicitly selected saved receipts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.review_overview import build_review_overview


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True, help="Registered project ID")
    parser.add_argument("--native-summary", type=Path, help="Selected native summary or directory")
    parser.add_argument("--findings-view", type=Path, help="Selected findings review or directory")
    parser.add_argument("--parts-report", type=Path, help="Selected parts report or directory")
    parser.add_argument("--three-d-report", type=Path, help="Selected 3D report or directory")
    parser.add_argument("--charts-report", type=Path, help="Selected charts report or directory")
    parser.add_argument(
        "--verification-report", type=Path, help="Selected verification report or directory"
    )
    parser.add_argument("--output", type=Path, help="Fresh output directory under build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = build_review_overview(
            args.root,
            args.project,
            native_summary=args.native_summary,
            findings_view=args.findings_view,
            parts_report=args.parts_report,
            three_d_report=args.three_d_report,
            charts_report=args.charts_report,
            verification_report=args.verification_report,
            output=args.output,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"Project overview could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"Project review overview: {report.project_id}")
        for item in report.items:
            print(f"  {item.kind}: {item.status} · {item.freshness}")
        print(f"Open: {report.output_directory}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
