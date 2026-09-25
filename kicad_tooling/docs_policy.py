"""Thin command-line adapter for the Markdown documentation-policy engine."""
from __future__ import annotations

import argparse
from pathlib import Path

from .hwrepo.documentation import check


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = check(args.root)
    print(report.model_dump_json(indent=2))
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
