"""Verify one project through the shared project-verification operation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.doctor import NativeRunner
from .hwrepo.layout import default_project_root
from .hwrepo.models import ProjectVerificationReport
from .hwrepo.project_verification import (
    SelectionFailure,
    container_command,
    format_report,
    run_command,
    verify_request,
)
from .hwrepo.project_verification_models import (
    ProjectVerificationRequest,
    VerificationDetail,
)
from .hwrepo.project_verification_models import (
    VerificationDepth as Depth,
)

__all__ = [
    "Depth",
    "NativeRunner",
    "ProjectVerificationRequest",
    "SelectionFailure",
    "container_command",
    "format_report",
    "run_command",
    "verify",
    "verify_request",
]


def verify(
    root: Path,
    project_id: str,
    depth: Depth = "portable",
    runner: NativeRunner = "auto",
    cli: str = "kicad-cli",
    output: Path | None = None,
    detail: VerificationDetail = "brief",
    ngspice: str = "ngspice",
) -> ProjectVerificationReport:
    """Compatibility adapter for callers using the former positional API."""
    return verify_request(
        root,
        ProjectVerificationRequest(
            project_id=project_id,
            depth=depth,
            runner=runner,
            cli=cli,
            output=output,
            detail=detail,
            ngspice=ngspice,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True, help="One registered project ID")
    parser.add_argument(
        "--depth",
        choices=("portable", "native", "electrical"),
        default="portable",
        help="portable: requirements/budgets; native: add KiCad/grounding; electrical: add simulation preflight and all configured cases",
    )
    parser.add_argument(
        "--runner",
        choices=("auto", "local", "container"),
        default="auto",
        help="Native runner; auto prefers an exact local CLI, then pinned Docker",
    )
    parser.add_argument(
        "--cli",
        default="kicad-cli",
        help="Exact local KiCad CLI command or path (relative paths use the caller's cwd)",
    )
    parser.add_argument(
        "--ngspice", default="ngspice", help="Exact ngspice executable for electrical depth"
    )
    parser.add_argument("--output", type=Path, help="Fresh receipt path under ignored build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--detail", choices=("brief", "full"), default="brief")
    args = parser.parse_args()
    if args.format == "json" and args.detail != "brief":
        parser.error("--detail is for text; JSON already includes every finding")
    try:
        request = ProjectVerificationRequest(
            project_id=args.project,
            depth=args.depth,
            runner=args.runner,
            cli=args.cli,
            output=args.output,
            detail=args.detail,
            ngspice=args.ngspice,
        )
        result = verify_request(args.root, request)
    except (OSError, ValueError) as exc:
        print(f"Cannot create verification receipt: {exc}", file=sys.stderr)
        return 2
    print(
        result.model_dump_json(indent=2)
        if args.format == "json"
        else format_report(result, args.detail)
    )
    return 0 if result.status == "PASS" else (2 if result.status == "ERROR" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
