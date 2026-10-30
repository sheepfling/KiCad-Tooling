"""Compare authored product variant BOMs in an offline review receipt."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.product_variant_bom import compare_product_variants


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--product", required=True)
    parser.add_argument("--before-variant", required=True)
    parser.add_argument("--after-variant", required=True)
    parser.add_argument("--output", type=Path, help="Fresh directory under ignored build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = compare_product_variants(
            args.root,
            args.product,
            args.before_variant,
            args.after_variant,
            args.output,
        )
    except (OSError, ValueError) as exc:
        print(f"Product variant BOM comparison could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"Product variant BOM comparison: {report.status}")
        print(f"Receipt: {report.output_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
