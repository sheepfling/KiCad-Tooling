"""Export selected findings and project-authored reviewer notes across two revisions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.review_handoff import export_review_handoff


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True)
    parser.add_argument("--baseline", type=Path, required=True, help="Saved baseline overview")
    parser.add_argument("--candidate", type=Path, required=True, help="Saved candidate overview")
    parser.add_argument("--notes", type=Path, required=True, help="Project-owned reviewer notes")
    parser.add_argument("--fingerprint", action="append", required=True, help="Finding SHA-256")
    parser.add_argument("--output", type=Path, help="Fresh ignored build/ directory")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = export_review_handoff(
            args.root,
            args.project,
            args.baseline,
            args.candidate,
            args.notes,
            tuple(args.fingerprint),
            args.output,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"Review handoff could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"Review handoff: {report.project_id}")
        print(f"  Findings: {len(report.findings)}; notes: {len(report.notes)}")
        print(f"Open: {report.output_directory}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
