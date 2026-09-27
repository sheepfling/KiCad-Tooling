"""Run source-bound schematic design heuristics with project-owned review decisions."""

from __future__ import annotations

import argparse
from pathlib import Path

from .hwrepo.design_lint import inspect_summary, text_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--project", required=True, help="Registered pcb or schematic project ID")
    parser.add_argument(
        "--native-summary",
        type=Path,
        required=True,
        help="Source-bound native project summary.json with hashed sibling netlist.xml",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    root = args.root.resolve()
    summary = (
        args.native_summary if args.native_summary.is_absolute() else root / args.native_summary
    )
    report = inspect_summary(root, args.project, summary)
    print(report.model_dump_json(indent=2) if args.format == "json" else text_report(report))
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
