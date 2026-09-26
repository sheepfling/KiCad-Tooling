"""Choose reviewed parts, populate matching footprints and prepare an order list."""

from __future__ import annotations

import argparse
import hashlib
import shlex
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from .hwrepo.contract_coach import (
    AutoNetlistRunner,
    ContainerNetlistRunner,
    LocalNetlistRunner,
)
from .hwrepo.contracts import read_model
from .hwrepo.mcp_files import read_regular_bytes
from .hwrepo.models import SupplierHandoffPlan
from .hwrepo.part_picker import create_picker, resume_selection, selection
from .hwrepo.part_picker_view import (
    picker_text,
    save_picker,
    save_selection,
    selection_text,
)
from .hwrepo.parts_workflow import (
    init_preferences,
    load_preferences,
    local_path,
    new_receipt,
    prepare,
    save_report,
    text_report,
)
from .hwrepo.purchasing_preferences import save_parts_preferences
from .hwrepo.supplier_handoff import prepare_supplier_handoff, submit_supplier_handoff


def count(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use a whole number") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("Use zero or a positive whole number")
    return number


@contextmanager
def reviewed_source_map(
    root: Path, requested: Path, expected_sha256: str | None
) -> Generator[Path, None, None]:
    """When a digest is supplied, apply only the bytes that actually matched it."""
    if expected_sha256 is None:
        yield requested
        return
    content, _ = read_regular_bytes(local_path(root, requested), maximum=2 * 1024 * 1024)
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError("Reviewed plan changed; inspect it and use its current SHA-256")
    with tempfile.TemporaryDirectory(prefix=".parts-reviewed-", dir=root / "build") as temporary:
        path = Path(temporary) / "plan.json"
        path.write_bytes(content)
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Start: python -B -m kicad_tooling.parts --project YOUR_PROJECT --assist. "
            "Choose reviewed parts, preview and apply, then rerun without --picker for an order list."
        ),
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--project", required=True, help="ID shown by kicad_tooling.template list")
    parser.add_argument("--boards", type=count, help="Number of boards (default: saved value or 1)")
    parser.add_argument(
        "--spare-percent", type=count, help="Extra parts percent, 0–100 (default 0)"
    )
    parser.add_argument("--spare-minimum", type=count, help="Minimum extras per part (default 0)")
    parser.add_argument(
        "--preferences",
        type=Path,
        help="Saved JSON preferences; default: island docs/purchasing.json if present",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--init-preferences",
        type=Path,
        help="Create a new preferences JSON under this island's docs/ and exit",
    )
    mode.add_argument(
        "--save-preferences",
        action="store_true",
        help="Create/update island docs/purchasing.json; existing files need a digest",
    )
    parser.add_argument(
        "--expected-sha256",
        help="Current preferences, locked plan or reviewed supplier handoff SHA-256",
    )
    mode.add_argument(
        "--prepare-handoff",
        type=Path,
        help="Prepare an offline DigiKey handoff from a saved parts report",
    )
    mode.add_argument(
        "--submit-handoff",
        type=Path,
        help="Submit the reviewed handoff once to an external DigiKey review list",
    )
    parser.add_argument(
        "--allow-supplier-submissions",
        action="store_true",
        help="Permit --submit-handoff to disclose the reviewed BOM to DigiKey",
    )
    mode.add_argument(
        "--assist",
        action="store_true",
        help="Open one local page for automatic CAD, parts and ordering",
    )
    mode.add_argument(
        "--auto-models",
        action="store_true",
        help="Automatically resolve paired footprint models and preview their import",
    )
    mode.add_argument(
        "--cad-plan", type=Path, help="Apply a previously reviewed automatic CAD plan"
    )
    mode.add_argument(
        "--source-cad",
        metavar="LCSC_ID",
        help="Fetch and check an exact LCSC part, then preview its project-local CAD import",
    )
    mode.add_argument(
        "--import-cad", type=Path, help="Apply a previously reviewed sourced CAD import plan"
    )
    mode.add_argument(
        "--check-step",
        metavar="LCSC_ID",
        help="Prepare pinned KiCad STEP and WRL alignment views for one exact part",
    )
    mode.add_argument(
        "--picker",
        action="store_true",
        help="Open the guided catalog choices workflow in a local review page",
    )
    mode.add_argument(
        "--selection",
        type=Path,
        help="Preview a downloaded selection, or apply the resulting locked map",
    )
    mode.add_argument(
        "--sync-models",
        action="store_true",
        help="Preview model assignments from saved parts after KiCad's F8 update",
    )
    parser.add_argument(
        "--expected-mpn",
        help="Require the CAD provider to report this exact manufacturer part number",
    )
    parser.add_argument(
        "--refresh-cad",
        action="store_true",
        help="Explicitly fetch a fresh source snapshot with --source-cad or --check-step",
    )
    parser.add_argument(
        "--port",
        type=count,
        default=0,
        help="Local assistant port (default: choose an available port)",
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Print assistant URL without opening a browser"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply exactly a previously previewed, locked --selection map",
    )
    parser.add_argument(
        "--native-summary",
        type=Path,
        help="Reuse source-bound capture for the picker or order review",
    )
    parser.add_argument("--runner", choices=("auto", "local", "container"), default="auto")
    parser.add_argument("--cli", default="kicad-cli", help="Exact local KiCad CLI, if selected")
    parser.add_argument("--output", type=Path, help="Fresh receipt directory below ignored build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    handoff_mode = args.prepare_handoff is not None or args.submit_handoff is not None
    if handoff_mode and (
        any(
            value is not None
            for value in (
                args.native_summary,
                args.preferences,
                args.boards,
                args.spare_percent,
                args.spare_minimum,
            )
        )
        or args.runner != "auto"
        or args.cli != "kicad-cli"
        or args.apply
    ):
        parser.error(
            "Supplier handoff uses the saved review; omit capture, quantity and apply options"
        )
    if args.allow_supplier_submissions and args.submit_handoff is None:
        parser.error("--allow-supplier-submissions requires --submit-handoff")
    if args.submit_handoff is not None:
        if not args.allow_supplier_submissions or args.expected_sha256 is None:
            parser.error(
                "--submit-handoff requires --allow-supplier-submissions and --expected-sha256"
            )
        if args.output is not None:
            parser.error("Submission retains its own attempt receipt; omit --output")
    if (
        (args.expected_mpn is not None or args.refresh_cad)
        and args.source_cad is None
        and args.check_step is None
    ):
        parser.error("--expected-mpn and --refresh-cad require --source-cad or --check-step")
    if args.import_cad is not None and not args.apply:
        parser.error("--import-cad requires --apply; inspect the source diff before importing")
    if args.port > 65535:
        parser.error("--port must be 0–65535")
    if not args.assist and (args.port or args.no_browser):
        parser.error("--port and --no-browser require --assist")
    if (
        args.assist
        or args.auto_models
        or args.cad_plan is not None
        or args.source_cad is not None
        or args.import_cad is not None
        or args.check_step is not None
    ):
        if (
            any(
                value is not None
                for value in (
                    args.native_summary,
                    args.preferences,
                    args.boards,
                    args.spare_percent,
                    args.spare_minimum,
                )
            )
            or args.runner != "auto"
            or args.cli != "kicad-cli"
        ):
            parser.error(
                "Assistant and automatic CAD modes manage their own inputs; set order quantities in the assistant"
            )
        if args.assist and (args.output is not None or args.format != "text" or args.apply):
            parser.error(
                "--assist opens an interactive local server; omit --output, --format and --apply"
            )
    if args.cad_plan is not None and not args.apply:
        parser.error("--cad-plan requires --apply; inspect the source diff before applying")
    if args.boards == 0:
        parser.error("--boards must be at least 1")
    if args.spare_percent is not None and args.spare_percent > 100:
        parser.error("--spare-percent must be between 0 and 100")
    if (
        args.native_summary is not None
        or args.init_preferences is not None
        or args.save_preferences
    ) and (args.runner != "auto" or args.cli != "kicad-cli"):
        parser.error("--runner and --cli apply only to fresh capture")
    mutation = args.selection is not None or args.sync_models
    if args.apply and args.selection is None and args.cad_plan is None and args.import_cad is None:
        parser.error(
            "--apply requires a previously previewed --selection map, --cad-plan or --import-cad"
        )
    if args.native_summary is not None and (
        mutation or args.init_preferences is not None or args.save_preferences
    ):
        parser.error("--native-summary applies only to the picker or order review")
    if mutation and (args.runner != "auto" or args.cli != "kicad-cli"):
        parser.error("--runner and --cli apply only to fresh capture")
    if (args.picker or mutation) and any(
        value is not None
        for value in (
            args.preferences,
            args.boards,
            args.spare_percent,
            args.spare_minimum,
        )
    ):
        parser.error(
            "Set quantities with the order review; the picker preserves saved build preferences"
        )
    if (args.init_preferences is not None or args.save_preferences) and args.output is not None:
        parser.error("--output applies only to a parts review")
    if args.expected_sha256 is not None and not (
        args.save_preferences
        or args.submit_handoff is not None
        or (args.apply and (args.selection is not None or args.cad_plan is not None))
    ):
        parser.error(
            "--expected-sha256 applies only to preference saves, reviewed source apply or supplier submission"
        )
    root = args.root.resolve()
    try:
        if handoff_mode:
            requested = (
                args.prepare_handoff if args.prepare_handoff is not None else args.submit_handoff
            )
            assert requested is not None
            artifact = local_path(root, requested).relative_to(root).as_posix()
            if args.prepare_handoff is not None:
                handoff = prepare_supplier_handoff(
                    root,
                    args.project,
                    artifact,
                    new_receipt(root, args.project, args.output),
                )
            else:
                spec = read_model(local_path(root, requested), SupplierHandoffPlan)
                if spec.project_id != args.project:
                    raise ValueError("Supplier handoff belongs to a different project")
                assert args.expected_sha256 is not None
                handoff = submit_supplier_handoff(root, artifact, args.expected_sha256)
            print(
                handoff.model_dump_json(indent=2)
                if args.format == "json"
                else f"{handoff.status}: {handoff.handoff}\nReviewed SHA-256: {handoff.handoff_sha256}\n"
                f"Attempt receipt: {handoff.attempt_receipt or 'not submitted'}\n"
                "External review only; no purchase or build is authorized."
            )
            return 0 if handoff.status in {"PREPARED", "SENT"} else 1
        if args.save_preferences:
            preferences = load_preferences(
                root,
                args.project,
                args.preferences,
                args.boards,
                args.spare_percent,
                args.spare_minimum,
            )
            saved = save_parts_preferences(root, args.project, preferences, args.expected_sha256)
            print(
                saved.model_dump_json(indent=2)
                if args.format == "json"
                else f"{saved.status}: {saved.path}\nSHA-256: {saved.readback_sha256}"
            )
            return 0
        if args.assist:
            from .hwrepo.parts_assistant import serve

            serve(root, args.project, port=args.port, open_browser=not args.no_browser)
            return 0
        if args.check_step is not None:
            from .hwrepo import cad_source, cad_step

            output = new_receipt(root, args.project, args.output)
            source = cad_source.fetch(
                root,
                args.check_step,
                new_receipt(root, args.project, None),
                expected_mpn=args.expected_mpn,
                refresh=args.refresh_cad,
            )
            report = cad_step.review(root, args.project, source, output)
            if args.format == "json":
                print(report.model_dump_json(indent=2))
            else:
                print(f"{report.status}: STEP alignment review for {report.supplier_id}")
                for issue in report.issues:
                    print(issue)
                if report.status == "REVIEW":
                    print(f"Open paired views: {output / 'index.html'}")
                print(f"Receipt: {output}")
            return 0 if report.status == "REVIEW" else 1
        if args.source_cad is not None or args.import_cad is not None:
            from .hwrepo import cad_library, cad_source
            from .hwrepo.models import CadSourcingReview

            output = new_receipt(root, args.project, args.output)
            if args.source_cad is not None:
                sourced = cad_source.fetch(
                    root,
                    args.source_cad,
                    output,
                    expected_mpn=args.expected_mpn,
                    refresh=args.refresh_cad,
                )
                planned = None
                if sourced.status == "READY" and sourced.bundle_directory is not None:
                    planned = cad_library.plan(
                        root,
                        args.project,
                        Path(sourced.bundle_directory),
                        new_receipt(root, args.project, None),
                    )
                review = CadSourcingReview(
                    source=sourced, import_plan=planned, review_id=str(output)
                )
                (output / "cad-review.json").write_text(
                    review.model_dump_json(indent=2) + "\n", encoding="utf-8"
                )
                if args.format == "json":
                    print(review.model_dump_json(indent=2))
                else:
                    print(f"{sourced.status}: CAD source {sourced.supplier_id}")
                    if sourced.bundle is not None:
                        print(
                            f"Provider reports: {sourced.bundle.manufacturer} {sourced.bundle.mpn}"
                        )
                        print(f"Package: {sourced.bundle.package}")
                        print(
                            "Using a verified local cache"
                            if sourced.cache_hit
                            else "Saved a frozen provider snapshot"
                        )
                    for issue in sourced.issues:
                        print(issue)
                    if planned is not None:
                        print(f"{planned.status}: project CAD import")
                        for issue in planned.issues:
                            print(issue)
                        if planned.check is not None:
                            print(f"Symbol pins: {', '.join(planned.check.symbol_pins)}")
                            print(f"Footprint pads: {', '.join(planned.check.footprint_pads)}")
                        if planned.plan_path is not None:
                            print(f"Review: {planned.receipt_directory}")
                            command = shlex.join(
                                (
                                    "python",
                                    "-B",
                                    "-m",
                                    "kicad_tooling.parts",
                                    "--root",
                                    str(root),
                                    "--project",
                                    args.project,
                                    "--import-cad",
                                    planned.plan_path,
                                    "--apply",
                                )
                            )
                            print("Then: " + command)
                    print(f"Receipt: {output}")
                return (
                    0
                    if sourced.status == "READY"
                    and planned is not None
                    and planned.status == "PLAN"
                    else 1
                )
            assert args.import_cad is not None
            imported = cad_library.apply(root, args.project, args.import_cad, output)
            if args.format == "json":
                print(imported.model_dump_json(indent=2))
            else:
                print(f"{imported.status}: CAD import for {args.project}")
                for issue in imported.issues:
                    print(issue)
                if imported.status == "APPLIED":
                    print(
                        f"Choose {imported.symbol_id} in KiCad (A); its footprint follows Update PCB from Schematic (F8)."
                    )
                print(f"Receipt: {imported.receipt_directory}")
            return 0 if imported.status == "APPLIED" else 1
        if args.auto_models or args.cad_plan is not None:
            from .hwrepo import auto_cad

            output = new_receipt(root, args.project, args.output)
            if args.auto_models:
                cad = auto_cad.plan(root, args.project, output)
            else:
                assert args.cad_plan is not None
                with reviewed_source_map(root, args.cad_plan, args.expected_sha256) as source_map:
                    cad = auto_cad.apply(root, args.project, source_map, output)
            if args.format == "json":
                print(cad.model_dump_json(indent=2))
            else:
                print(f"{cad.status}: automatic CAD for {args.project}")
                for item in cad.items:
                    print(f"  {item.reference}: {item.status} — {item.detail}")
                for issue in cad.issues:
                    print(issue)
                print(f"Receipt: {cad.receipt_directory}")
                if cad.plan_path is not None and not args.apply:
                    print(
                        f"Review cad.diff, then: python -B -m kicad_tooling.parts --project {args.project} --cad-plan {cad.plan_path} --apply"
                    )
            return 1 if cad.status in {"BLOCKED", "NEEDS_REVIEW"} or cad.issues else 0
        if args.init_preferences is not None:
            preferences = load_preferences(
                root,
                args.project,
                args.preferences,
                args.boards,
                args.spare_percent,
                args.spare_minimum,
            )
            path = init_preferences(root, args.project, args.init_preferences, preferences)
            if args.format == "json":
                print(preferences.model_dump_json(indent=2))
            else:
                print(
                    f"Saved preferences: {path}\nEdit reviewed DigiKey SKUs here if needed.\n"
                    "Next: python -B -m kicad_tooling.parts --project "
                    + args.project
                    + " --preferences "
                    + path.relative_to(root).as_posix()
                )
            return 0
        output = new_receipt(root, args.project, args.output)
        runner = (
            LocalNetlistRunner(args.cli)
            if args.runner == "local"
            else ContainerNetlistRunner()
            if args.runner == "container"
            else AutoNetlistRunner(args.cli)
        )
        if args.picker:
            picker = create_picker(root, args.project, output, runner, args.native_summary)
            save_picker(output, picker)
            print(
                picker.model_dump_json(indent=2) if args.format == "json" else picker_text(picker)
            )
            return 0 if picker.status == "READY" else 1
        if mutation:
            if args.selection is not None:
                with reviewed_source_map(root, args.selection, args.expected_sha256) as source_map:
                    result = selection(root, args.project, source_map, output, apply=args.apply)
            else:
                result = resume_selection(root, args.project, output)
            save_selection(output, result)
            print(
                result.model_dump_json(indent=2)
                if args.format == "json"
                else selection_text(result)
            )
            return 1 if result.status == "BLOCKED" else 0
        report = prepare(
            root,
            args.project,
            output,
            runner,
            args.native_summary,
            args.preferences,
            args.boards,
            args.spare_percent,
            args.spare_minimum,
        )
        save_report(output, report)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(report.model_dump_json(indent=2) if args.format == "json" else text_report(report))
    return 0 if report.status == "READY_FOR_ORDER_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
