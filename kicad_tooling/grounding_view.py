"""Export one source-bound grounding relationship as an offline review."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.grounding_view import build_grounding_view
from .hwrepo.layout import default_project_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument(
        "--receipt", type=Path, required=True, help="Saved electrical.json or directory"
    )
    parser.add_argument("--net", required=True, help="Exact authored ground net")
    parser.add_argument("--output", type=Path, help="Fresh directory under ignored build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = build_grounding_view(args.root, args.receipt, args.net, args.output)
    except (OSError, ValueError) as exc:
        print(f"Grounding view could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"Grounding view: {report.net} ({report.observation_status})")
        print(f"Receipt: {report.output_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
