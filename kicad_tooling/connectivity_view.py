"""Export exact net membership and one adjacent component hop offline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.connectivity_view import build_connectivity_view
from .hwrepo.layout import default_project_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--net", required=True)
    parser.add_argument("--output", type=Path, help="Fresh directory under ignored build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = build_connectivity_view(args.root, args.receipt, args.net, args.output)
    except (OSError, ValueError, TypeError) as exc:
        print(f"Connectivity view could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"Connectivity: {report.net} ({len(report.components)} components)")
        print(f"Open: {report.output_directory}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
