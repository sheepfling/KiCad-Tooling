"""Compare two selected saved project overviews and optional release manifests."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.verification_history import compare_verification_history


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True, help="Registered project ID")
    parser.add_argument("--baseline", type=Path, required=True, help="Saved baseline overview.json")
    parser.add_argument(
        "--candidate", type=Path, required=True, help="Saved candidate overview.json"
    )
    parser.add_argument("--baseline-release", type=Path, help="Explicit baseline release manifest")
    parser.add_argument(
        "--candidate-release", type=Path, help="Explicit candidate release manifest"
    )
    parser.add_argument("--output", type=Path, help="Fresh ignored build/ output directory")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = compare_verification_history(
            args.root,
            args.project,
            args.baseline,
            args.candidate,
            baseline_release=args.baseline_release,
            candidate_release=args.candidate_release,
            output=args.output,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"Verification history could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"Verification history: {report.project_id}")
        print(f"  Source: {report.baseline.source_relation} → {report.candidate.source_relation}")
        print(f"  Checks: {len(report.check_changes)}; findings: {len(report.finding_changes)}")
        print(f"Open: {report.output_directory}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
