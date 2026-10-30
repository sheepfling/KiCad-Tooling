"""Explore one authored product variant's assembly and connections offline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.product_visual import build_product_visual


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--product", required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--output", type=Path, help="Fresh directory under ignored build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = build_product_visual(args.root, args.product, args.variant, args.output)
    except (OSError, ValueError) as exc:
        print(f"Product visual review could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"Product visual review: {report.status}")
        print(f"Receipt: {report.output_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
