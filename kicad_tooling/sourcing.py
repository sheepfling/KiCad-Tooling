"""Validate a typed, manually captured supplier-offer snapshot without network access."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.contracts import read_model, repo_path
from .hwrepo.models import PolicyIssue, SourcingSnapshot, SourcingSnapshotReport
from .hwrepo.sourcing import check


def format_sourcing(report: SourcingSnapshotReport, *, limit: int = 5) -> str:
    """Summarize a snapshot without treating its offers as purchase approval."""
    lines = [
        f"Sourcing snapshot {report.snapshot_id}: {report.status}",
        f"Offers: {report.offers}",
        f"Issues: {len(report.issues)}",
    ]
    for issue in report.issues[:limit]:
        lines.append(f"  - {issue.code} at {issue.location}: {issue.message}")
    if len(report.issues) > limit:
        lines.append("  More findings are available with --format json.")
    lines.append("Build authorized: no; validate sourcing separately from purchase approval.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, help="Repository-relative sourcing snapshot")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Machine JSON (default) or a concise human summary",
    )
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        result = check(root, read_model(repo_path(root, args.snapshot), SourcingSnapshot))
    except (OSError, ValueError) as exc:
        result = SourcingSnapshotReport(
            snapshot_id="unreadable-snapshot",
            offers=0,
            status="FAIL",
            issues=(
                PolicyIssue(
                    code="SOURCING_LOAD",
                    location=args.snapshot,
                    message=str(exc),
                ),
            ),
        )
        print(str(exc), file=sys.stderr)
    print(format_sourcing(result) if args.format == "text" else result.model_dump_json(indent=2))
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
