"""Typed template diagnostics, adoption, scaffolding and migration command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.adoption import adopt
from .hwrepo.cli_output import summary
from .hwrepo.diagnostic_journal import DiagnosticJournal
from .hwrepo.diagnostics import diagnose_import, diagnose_project, format_text
from .hwrepo.doctor import doctor
from .hwrepo.foreign_pcb import convert_pcb
from .hwrepo.foreign_pcb import render_text as render_foreign_pcb
from .hwrepo.import_inventory import format_import_inventory, scan_imports
from .hwrepo.importing import import_project
from .hwrepo.initialization import initialize
from .hwrepo.inventory import format_inventory, inventory
from .hwrepo.models import ProjectKind
from .hwrepo.rescue import format_rescue, rescue_project
from .hwrepo.scaffold import new_project
from .hwrepo.template import bootstrap, plan_upgrade, preflight


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "doctor",
            "adopt",
            "init",
            "preflight",
            "bootstrap",
            "upgrade-plan",
            "new-project",
            "import-project",
            "convert-pcb",
            "scan-imports",
            "diagnose",
            "rescue",
            "list",
        ),
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--project-id")
    parser.add_argument("--target-version")
    parser.add_argument("--kind", choices=[kind.value for kind in ProjectKind], default="pcb")
    parser.add_argument("--toolchain")
    parser.add_argument(
        "--cli",
        default="kicad-cli",
        help="KiCad CLI for doctor or convert-pcb (relative paths use the caller's cwd)",
    )
    parser.add_argument(
        "--native",
        action="store_true",
        help="Require doctor to find this project's exact local CLI or pinned Docker runner",
    )
    parser.add_argument(
        "--runner",
        choices=("auto", "local", "container"),
        default="auto",
        help="Native runner for doctor --native/--electrical or convert-pcb; auto prefers an exact local CLI, then Docker",
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Native .kicad_pro for import/diagnose, or foreign board file for convert-pcb",
    )
    parser.add_argument(
        "--input-format",
        choices=("auto", "pads", "altium", "eagle", "cadstar", "fabmaster", "pcad", "solidworks"),
        help="Foreign PCB format for convert-pcb (default: auto)",
    )
    parser.add_argument(
        "--electrical",
        action="store_true",
        help="Doctor: require native and electrical setup plus the exact host ngspice",
    )
    parser.add_argument(
        "--ngspice", default="ngspice", help="Simulator executable for doctor --electrical"
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Directory of candidate .kicad_pro files to inventory without copying",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview an import without writing files"
    )
    parser.add_argument("--native-report", type=Path, help="Project native summary.json to explain")
    parser.add_argument(
        "--bom", type=Path, help="Native assembly/bom.csv to check for part identities"
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        help="Output format (default: text for diagnose/rescue, JSON otherwise)",
    )
    parser.add_argument(
        "--detail",
        choices=("brief", "full"),
        help="Text detail for diagnose/rescue (default: brief; JSON is always full)",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        help="New diagnose/rescue receipt directory (default: ignored build/diagnostics)",
    )
    args = parser.parse_args()
    if (
        args.command not in {"import-project", "convert-pcb", "diagnose"}
        and args.source is not None
    ):
        parser.error("--source requires import-project, convert-pcb or diagnose")
    if args.command != "convert-pcb" and args.input_format is not None:
        parser.error("--input-format requires convert-pcb")
    if args.command != "scan-imports" and args.source_dir is not None:
        parser.error("--source-dir requires scan-imports")
    if args.command != "import-project" and args.dry_run:
        parser.error("--dry-run options require import-project")
    if args.command != "diagnose" and (args.native_report or args.bom):
        parser.error("--native-report and --bom require diagnose")
    if args.command not in {"diagnose", "rescue"} and (
        args.detail is not None or args.log_dir is not None
    ):
        parser.error("--detail and --log-dir require diagnose or rescue")
    if args.command != "doctor" and args.electrical:
        parser.error("--electrical requires doctor")
    if args.ngspice != "ngspice" and not args.electrical:
        parser.error("--ngspice requires doctor --electrical")
    if args.command != "doctor" and args.native:
        parser.error("--native requires doctor")
    if args.command not in {"doctor", "convert-pcb"} and args.runner != "auto":
        parser.error("--runner requires doctor or convert-pcb")
    if args.command == "doctor" and not (args.native or args.electrical) and args.runner != "auto":
        parser.error("--runner requires --native or --electrical")
    if args.command == "doctor":
        result = doctor(
            args.root,
            args.native,
            args.toolchain,
            args.cli,
            project_id=args.project_id,
            runner=args.runner,
            electrical=args.electrical,
            ngspice=args.ngspice,
        )
    elif args.command == "rescue":
        if args.project_id is None:
            parser.error("rescue requires --project-id")
        if args.toolchain is not None:
            parser.error("rescue reads the selected project's declared toolchain")
        if args.format == "json" and args.detail is not None:
            parser.error("--detail is for text; JSON already includes every finding")
        try:
            journal = DiagnosticJournal(args.root, args.project_id, args.log_dir)
        except (OSError, ValueError) as exc:
            print(f"Cannot create rescue log: {exc}", file=sys.stderr)
            return 2
        try:
            result = rescue_project(args.root, args.project_id, journal)
            human_text = format_rescue(result, args.detail or "brief")
            journal.finish(result, human_text, result.status)
        except Exception as exc:  # noqa: BLE001 - retain unexpected tool errors in receipt
            journal.fail(exc)
            print(
                f"Rescue stopped: {type(exc).__name__}: {exc}\n"
                f"Full traceback: {journal.directory / 'error.txt'}",
                file=sys.stderr,
            )
            return 2
        except KeyboardInterrupt as exc:
            journal.fail(exc)
            print(f"Rescue interrupted; run log: {journal.directory}", file=sys.stderr)
            return 130
        print(result.model_dump_json(indent=2) if args.format == "json" else human_text)
        return 1  # A local rescue is never a CI or release acceptance result.
    elif args.command == "adopt":
        if args.project_id is None:
            parser.error("adopt requires --project-id (the repository identity)")
        result = adopt(args.root, args.project_id)
    elif args.command == "init":
        if args.project_id is None:
            parser.error("init requires --project-id (the repository identity)")
        result = initialize(args.root, args.project_id)
    elif args.command == "import-project":
        if args.project_id is None or args.toolchain is None or args.source is None:
            parser.error("import-project requires --source, --project-id and --toolchain")
        result = import_project(
            args.root, args.source, args.project_id, args.toolchain, args.dry_run
        )
    elif args.command == "convert-pcb":
        if args.project_id is None or args.toolchain is None or args.source is None:
            parser.error("convert-pcb requires --source, --project-id and --toolchain")
        result = convert_pcb(
            args.root,
            args.source,
            args.project_id,
            args.toolchain,
            args.input_format or "auto",
            args.runner,
            args.cli,
        )
        print(
            render_foreign_pcb(result)
            if args.format != "json"
            else result.model_dump_json(indent=2)
        )
        return 0 if result.status == "PASS" else 1
    elif args.command == "scan-imports":
        if args.source_dir is None or args.toolchain is None:
            parser.error("scan-imports requires --source-dir and --toolchain")
        report = scan_imports(args.root, args.source_dir, args.toolchain)
        print(
            format_import_inventory(report)
            if args.format == "text"
            else report.model_dump_json(indent=2)
        )
        return 0 if report.status == "PASS" else 1
    elif args.command == "diagnose":
        if args.project_id is None:
            parser.error("diagnose requires --project-id")
        if args.format == "json" and args.detail is not None:
            parser.error("--detail is for text; JSON already includes every finding")
        if args.source is not None:
            if args.toolchain is None or args.native_report or args.bom:
                parser.error(
                    "diagnose --source requires --toolchain and cannot use native/BOM reports"
                )
        else:
            if args.toolchain is not None:
                parser.error("diagnose --toolchain requires --source")
            if args.bom is not None and args.native_report is None:
                parser.error("diagnose --bom requires --native-report for the selected project")
        try:
            journal = DiagnosticJournal(args.root, args.project_id, args.log_dir)
        except (OSError, ValueError) as exc:
            print(
                f"Cannot create diagnostic log: {exc}. Use --log-dir outside the repository "
                "or repair build/ permissions.",
                file=sys.stderr,
            )
            return 2
        try:
            if args.source is not None:
                assert args.toolchain is not None
                result = diagnose_import(
                    args.root, args.source, args.project_id, args.toolchain, journal
                )
            else:
                result = diagnose_project(
                    args.root, args.project_id, args.native_report, args.bom, journal
                )
            result = result.model_copy(update={"run_directory": str(journal.directory)})
            human_text = format_text(result, args.detail or "brief")
            journal.finish(result, human_text, result.status)
        except Exception as exc:  # noqa: BLE001 - CLI boundary must retain unexpected tracebacks
            journal.fail(exc)
            print(
                f"Diagnosis stopped: {type(exc).__name__}: {exc}\n"
                f"Repair the input or tool; full traceback: {journal.directory / 'error.txt'}",
                file=sys.stderr,
            )
            return 2
        except KeyboardInterrupt as exc:
            journal.fail(exc)
            print(f"Diagnosis interrupted; run log: {journal.directory}", file=sys.stderr)
            return 130
        print(result.model_dump_json(indent=2) if args.format == "json" else human_text)
        return 0 if result.status == "PASS" else 1
    elif args.command == "new-project":
        if args.project_id is None or args.toolchain is None:
            parser.error("new-project requires --project-id and --toolchain")
        result = new_project(args.root, args.project_id, ProjectKind(args.kind), args.toolchain)
    elif args.command == "list":
        result = inventory(args.root)
        print(
            format_inventory(result) if args.format == "text" else result.model_dump_json(indent=2)
        )
        return 0 if result.status == "PASS" else 1
    elif args.command == "preflight":
        result = preflight(args.root)
    elif args.command == "bootstrap":
        if args.destination is None or args.project_id is None:
            parser.error("bootstrap requires --destination and --project-id")
        result = bootstrap(args.root, args.destination, args.project_id)
    else:
        if args.target_version is None:
            parser.error("upgrade-plan requires --target-version")
        result = plan_upgrade(args.root, args.target_version)
    print(
        summary(f"Template {args.command}", result)
        if args.format == "text"
        else result.model_dump_json(indent=2)
    )
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
