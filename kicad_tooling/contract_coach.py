"""Compare source-bound, UNREVIEWED KiCad netlist observations with an authored contract."""
from __future__ import annotations

import argparse
from pathlib import Path

from .hwrepo.contract_coach import (
    AutoNetlistRunner,
    ContainerNetlistRunner,
    LocalNetlistRunner,
    capture,
    inspect_summary,
    receipt_directory,
    save_receipt,
    text_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--project-id", required=True, help="Registered pcb or schematic project ID")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--native-summary", type=Path,
        help="Existing project summary.json with a hashed sibling netlist.xml",
    )
    mode.add_argument(
        "--capture", action="store_true",
        help="Export a fresh netlist into a new ignored receipt even if the contract is empty",
    )
    parser.add_argument("--cli", default="kicad-cli", help="Exact catalogued local KiCad CLI for --capture")
    parser.add_argument(
        "--runner", choices=("auto", "local", "container"), default="auto",
        help="Capture with exact local KiCad when available, else the digest-pinned Docker image",
    )
    parser.add_argument(
        "--output", type=Path,
        help="Fresh ignored build/ receipt; --capture creates one automatically if omitted",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--detail", choices=("brief", "full"), default="brief")
    args = parser.parse_args()
    if args.format == "json" and args.detail != "brief":
        parser.error("--detail is for text; JSON already includes the full inventory")
    if args.native_summary is not None and args.cli != "kicad-cli":
        parser.error("--cli applies only to --capture")
    if args.native_summary is not None and args.runner != "auto":
        parser.error("--runner applies only to --capture")
    root = args.root.resolve()
    try:
        receipt = (
            receipt_directory(root, args.project_id, args.output)
            if args.capture or args.output is not None else None
        )
        if args.capture:
            if receipt is None:
                raise ValueError("Capture requires a new ignored receipt")
            runner = (
                LocalNetlistRunner(args.cli) if args.runner == "local"
                else ContainerNetlistRunner() if args.runner == "container"
                else AutoNetlistRunner(args.cli)
            )
            report = capture(root, args.project_id, receipt, runner)
        else:
            if args.native_summary is None:
                raise ValueError("Select --capture or --native-summary")
            summary = (
                args.native_summary if args.native_summary.is_absolute()
                else root / args.native_summary
            )
            report = inspect_summary(root, args.project_id, summary)
            if receipt is not None:
                report = report.model_copy(update={"receipt_dir": str(receipt)})
        if receipt is not None:
            save_receipt(receipt, report)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(report.model_dump_json(indent=2) if args.format == "json" else text_report(report, args.detail))
    return 0 if report.status == "READY_FOR_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
