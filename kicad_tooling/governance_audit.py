"""Inspect hosted GitHub governance without changing settings or repository files."""
from __future__ import annotations

import argparse
from pathlib import Path

from .hwrepo.hosted_governance import audit, format_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="Local repository containing catalog/team-policy.json")
    parser.add_argument("--repo", help="GitHub OWNER/REPO (default: current gh repository)")
    parser.add_argument("--record", help="Optional project governance record relative to --root")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args()
    report = audit(args.root, args.repo, args.record)
    print(format_text(report) if args.format == "text" else report.model_dump_json(indent=2))
    return {"PASS": 0, "NEEDS_SETUP": 1, "UNKNOWN": 2}[report.status]


if __name__ == "__main__":
    raise SystemExit(main())
