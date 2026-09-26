"""Serve the optional local KiCad workflow MCP interface over stdio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, required=True, help="Absolute path to the trusted repository checkout"
    )
    parser.add_argument(
        "--allow-checks",
        action="store_true",
        help="Expose project verification, which executes repository code",
    )
    parser.add_argument(
        "--allow-writes",
        action="store_true",
        help="Expose creation and import of new project islands",
    )
    parser.add_argument(
        "--allow-edits",
        action="store_true",
        help="Expose reviewed, hash-checked replacements of existing project text",
    )
    parser.add_argument(
        "--allow-exports",
        action="store_true",
        help="Expose packaging/restore; native export and review also need --allow-checks",
    )
    parser.add_argument(
        "--allow-downloads",
        action="store_true",
        help="Allow official and exact-part community CAD downloads in enabled tools",
    )
    parser.add_argument(
        "--allow-supplier-submissions",
        action="store_true",
        help="Expose explicit reviewed BOM submission to DigiKey; never places an order",
    )
    parser.add_argument(
        "--import-root",
        type=Path,
        action="append",
        default=[],
        help="Additional absolute directory permitted for import reads; repeatable",
    )
    args = parser.parse_args()
    if not args.root.is_absolute() or any(not path.is_absolute() for path in args.import_root):
        parser.error("--root and --import-root must be absolute paths")
    try:
        from .hwrepo.mcp_server import create_server
    except ModuleNotFoundError as exc:
        if exc.name == "mcp" or (exc.name is not None and exc.name.startswith("mcp.")):
            print(
                "MCP support is not installed. Install kicad-team-tooling[mcp] "
                "or add the mcp extra to your local tooling installation.",
                file=sys.stderr,
            )
            return 2
        raise
    try:
        server = create_server(
            args.root,
            allow_checks=args.allow_checks,
            allow_writes=args.allow_writes,
            import_roots=tuple(args.import_root),
            allow_edits=args.allow_edits,
            allow_exports=args.allow_exports,
            allow_downloads=args.allow_downloads,
            allow_supplier_submissions=args.allow_supplier_submissions,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
