"""Navigate a source-matched parts review on retained schematic and PCB plots."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.cross_probe import build_cross_probe
from .hwrepo.layout import default_project_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True)
    parser.add_argument("--parts-report", type=Path, required=True)
    parser.add_argument("--findings-view", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Fresh directory under ignored build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = build_cross_probe(
            args.root, args.project, args.parts_report, args.findings_view, args.output
        )
    except (OSError, ValueError) as exc:
        print(f"BOM cross-probe could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        mapped = sum(bool(entry.board or entry.schematic) for entry in report.entries)
        print(f"BOM cross-probe: {mapped}/{len(report.entries)} references located")
        print(f"Receipt: {report.output_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
