"""Export an offline schematic and PCB review from saved native evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.findings_view import build_findings_view
from .hwrepo.layout import default_project_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True, help="Registered project ID")
    parser.add_argument(
        "--native-summary", type=Path, required=True, help="Saved native receipt or summary.json"
    )
    parser.add_argument("--lint-report", type=Path, help="Optional saved design-lint JSON snapshot")
    parser.add_argument("--output", type=Path, help="Fresh receipt directory under build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = build_findings_view(
            args.root, args.project, args.native_summary, args.output, args.lint_report
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"Findings review could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        mapped = sum(bool(item.markers) for item in report.findings)
        print(
            f"Findings review: {report.project_id}\n"
            f"Native checks: {report.native_status}; design lint: {report.lint_status}\n"
            f"Findings: {len(report.findings)}; with markers: {mapped}\n"
            f"Open: {report.output_directory}/index.html"
        )
        for issue in report.issues:
            print(f"Coverage: {issue}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
