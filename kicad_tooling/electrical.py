"""Set up or run grounding, power and high-frequency circuit checks."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .hwrepo.cli_output import summary
from .hwrepo.contract_coach import (
    AutoNetlistRunner,
    ContainerNetlistRunner,
    LocalNetlistRunner,
    NetlistRunner,
)
from .hwrepo.electrical_runner import analyze, format_report
from .hwrepo.electrical_setup import capture_inputs, initialize


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Start with --init, capture model hashes with --capture-inputs, review the contract, "
        "then run kicad_tooling.template doctor --electrical --project-id <id>. "
        "Guide: docs/workflow/ELECTRICAL_ANALYSIS.md",
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--project", required=True, help="Registered board or schematic ID")
    setup = parser.add_mutually_exclusive_group()
    setup.add_argument(
        "--init",
        action="store_true",
        help="Create and connect a pending contract; never overwrite existing requirements",
    )
    setup.add_argument(
        "--capture-inputs",
        action="store_true",
        help="Write UNREVIEWED design/model hashes under build/; never update approved bindings",
    )
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="Repository-relative deck or include for --capture-inputs; repeat for dependencies",
    )
    parser.add_argument(
        "--ngspice-version", help="Engineer-selected version for --init; otherwise UNREVIEWED"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Fresh analysis/input receipt directory below build/; unavailable with --init",
    )
    parser.add_argument(
        "--native-summary",
        type=Path,
        help="Reuse a current source-bound native project summary for analysis",
    )
    parser.add_argument(
        "--runner",
        choices=("auto", "local", "container"),
        default="auto",
        help="KiCad netlist runner; ngspice runs on the host",
    )
    parser.add_argument("--cli", default="kicad-cli", help="Exact local KiCad executable")
    parser.add_argument(
        "--ngspice", default="ngspice", help="Exact contract-pinned host simulator executable"
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--detail",
        choices=("brief", "full"),
        default="brief",
        help="Analysis text detail; JSON always includes every result",
    )
    args = parser.parse_args()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.project) is None:
        parser.error("Invalid project ID")
    if args.model and not args.capture_inputs:
        parser.error("--model requires --capture-inputs")
    if args.ngspice_version is not None and not args.init:
        parser.error("--ngspice-version requires --init")
    if args.init and args.output is not None:
        parser.error("--init writes the project contract; --output is only for ignored receipts")
    if (args.init or args.capture_inputs) and (
        args.native_summary
        or args.runner != "auto"
        or args.cli != "kicad-cli"
        or args.ngspice != "ngspice"
    ):
        parser.error(
            "Setup does not run native tools; omit --native-summary, --runner, --cli and --ngspice"
        )
    if args.detail != "brief" and (args.format == "json" or args.init or args.capture_inputs):
        parser.error("--detail full applies only to analysis text output")
    try:
        if args.init:
            created = initialize(args.root, args.project, args.ngspice_version or "UNREVIEWED")
            print(
                created.model_dump_json(indent=2)
                if args.format == "json"
                else summary("Electrical setup", created)
            )
            return 0
        if args.capture_inputs:
            inventory = capture_inputs(args.root, args.project, tuple(args.model), args.output)
            print(
                inventory.model_dump_json(indent=2)
                if args.format == "json"
                else (
                    summary("Electrical input capture", inventory)
                    + f"\nCaptured: {len(inventory.source_sha256)} design files, {len(inventory.model_sha256)} model files"
                    + f"\nHashes: {inventory.run_directory}/inputs.json"
                )
            )
            return 0
        runner: NetlistRunner = (
            LocalNetlistRunner(args.cli)
            if args.runner == "local"
            else ContainerNetlistRunner()
            if args.runner == "container"
            else AutoNetlistRunner(args.cli)
        )
        report = analyze(
            args.root,
            args.project,
            args.output,
            args.native_summary,
            args.cli,
            args.ngspice,
            runner,
        )
    except (OSError, ValueError) as exc:
        print(f"Electrical command could not finish: {exc}", file=sys.stderr)
        return 2
    print(
        report.model_dump_json(indent=2)
        if args.format == "json"
        else format_report(report, args.detail)
    )
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
