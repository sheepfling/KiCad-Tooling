"""Save a source-linked release readiness check and offline issue view."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.release_readiness_view import capture_release_readiness


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Fresh directory under ignored build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = capture_release_readiness(args.root, args.manifest, args.output)
    except (OSError, ValueError, TypeError) as exc:
        print(f"Release readiness view could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(
            f"Release readiness: {report.readiness.status} ({len(report.readiness.issues)} issues)"
        )
        print(f"Open: {report.output_directory}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
