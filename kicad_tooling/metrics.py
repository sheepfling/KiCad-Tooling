"""Print typed, read-only current metrics for template policy and release deviations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.contracts import read_model, repo_path
from .hwrepo.metrics import collect
from .hwrepo.models import ReleaseManifest, TemplateMetricsReport


def format_metrics(report: TemplateMetricsReport) -> str:
    """Show each current check and deviation count without granting authority."""
    passing = sum(check.status == "PASS" for check in report.checks)
    lines = [f"Template metrics: {passing}/{len(report.checks)} checks pass"]
    for check in report.checks:
        lines.append(f"  {check.name}: {check.status} ({check.findings} findings)")
    lines.append(f"Stale evidence: {report.stale_evidence}")
    deviations = report.deviations
    lines.append(
        f"Deviations: {deviations.total} total; {deviations.open} open, "
        f"{deviations.approved} approved, {deviations.closed} closed, "
        f"{deviations.expired} expired"
    )
    if passing != len(report.checks):
        lines.append("Next: run python -B -m kicad_tooling.ci for detailed policy findings.")
    lines.append("Build authorized: no; these are current, read-only metrics.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", help="Optional repository-relative release manifest")
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Machine JSON (default) or a concise human summary",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        deviations = (
            ()
            if args.manifest is None
            else read_model(repo_path(root, args.manifest), ReleaseManifest).deviations
        )
        result = collect(root, deviations)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(format_metrics(result) if args.format == "text" else result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
