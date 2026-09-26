"""Report tracked CLI/MCP capabilities, intentional gaps and declaration drift."""
from __future__ import annotations

import argparse
from pathlib import Path

from .hwrepo.surface import format_surfaces, inspect_tool_surfaces


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--require-live-mcp", action="store_true",
                        help="Fail if the optional MCP SDK cannot verify full registration")
    args = parser.parse_args()
    report = inspect_tool_surfaces(args.root, require_live_mcp=args.require_live_mcp)
    print(report.model_dump_json(indent=2) if args.format == "json" else format_surfaces(report))
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
