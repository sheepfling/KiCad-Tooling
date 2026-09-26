"""Convert one foreign PCB into an ignored, reviewable KiCad import preview."""
from __future__ import annotations

import hashlib
import re
import shlex
from pathlib import Path
from typing import Literal

from ..check_toolchain import cli_executable, toolchain
from .contract_coach import docker_prefix, pinned_image, run_command
from .contracts import read_kicad_import_summary
from .diagnostic_journal import DiagnosticJournal
from .doctor import NativeRunner, doctor
from .importing import import_project
from .models import (
    CommandEvidence,
    ForeignFormat,
    ForeignPcbReport,
    KiCadForeignImportSummary,
    ProjectImportReport,
)


def render_text(report: ForeignPcbReport) -> str:
    lines = [f"Foreign PCB conversion: {report.status}", f"Project: {report.project_id}",
             f"Toolchain: {report.toolchain_id}; runner: {report.runner}",
             f"Receipt: {report.run_directory}"]
    if report.board_sha256:
        lines.append(f"Converted board SHA-256: {report.board_sha256}")
    if report.native_summary is not None:
        lines.append(f"KiCad report: {report.native_summary.mapped_layers} mapped layers, "
                     f"{len(report.native_summary.errors)} errors, "
                     f"{len(report.native_summary.warnings)} warnings")
        for warning in report.native_summary.warnings[:3]:
            lines.append(f"KiCad warning: {warning}")
        if len(report.native_summary.warnings) > 3:
            lines.append("More warnings: open kicad-import-report.json in the receipt")
    if report.error:
        lines.append(f"Finding: {report.error}")
    for action in report.next_actions:
        lines.append(f"Next: {action}")
    if report.next_command:
        lines.append(f"After review: {report.next_command}")
    return "\n".join(lines)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def convert_pcb(
    root: Path, source: Path, project_id: str, toolchain_id: str,
    input_format: ForeignFormat = "auto", runner: NativeRunner = "auto", cli: str = "kicad-cli",
) -> ForeignPcbReport:
    """Never touch the source or register a project; require a separate reviewed import."""
    root = root.resolve()
    journal = DiagnosticJournal(root, project_id, label="convert-pcb")
    source = source.absolute()
    source_hash: str | None = None
    selected: Literal["none", "local", "container"] = "none"
    commands: dict[str, CommandEvidence] = {}
    native_summary: KiCadForeignImportSummary | None = None
    board_hash: str | None = None
    preview: ProjectImportReport | None = None
    next_command: str | None = None
    error: str | None = None
    actions: tuple[str, ...] = ()
    status: Literal["PASS", "FAIL"] = "FAIL"
    try:
        with journal.stage("project-selection"):
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", project_id) is None:
                raise ValueError("Project ID must use letters, digits, periods, underscores or hyphens")
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", toolchain_id) is None:
                raise ValueError("Toolchain ID must use letters, digits, periods, underscores or hyphens")
            if input_format not in ForeignFormat.__args__:
                raise ValueError(f"Unknown foreign PCB format: {input_format}")
        with journal.stage("source-and-toolchain"):
            if source.is_symlink() or not source.is_file() or source.suffix == ".kicad_pcb":
                raise ValueError("Select one existing non-KiCad PCB file (not a symlink or native board)")
            source_hash = _digest(source)
            record = toolchain(root, toolchain_id)
            stage = journal.directory / "stage"
            stage.mkdir()
            board = stage / f"{project_id}.kicad_pcb"
            native_project = stage / f"{project_id}.kicad_pro"
            native_report = journal.directory / "kicad-import-report.json"
        with journal.stage("runner-readiness"):
            ready = doctor(root, native=True, toolchain_id=toolchain_id, cli=cli, runner=runner)
            journal.save_model("doctor", ready)
            if ready.status != "PASS":
                raise ValueError("Exact KiCad runner unavailable; inspect doctor.json and run "
                                 f"kicad_tooling.template doctor --native --toolchain {toolchain_id}")
            choice = next(check.observed for check in ready.checks if check.id == "native-runner")
            if choice not in {"local", "container"}:
                raise ValueError("Doctor did not select a native runner")
            selected = "local" if choice == "local" else "container"
        if selected == "local":
            executable = cli_executable(cli)
            if executable is None:
                raise ValueError(f"Local KiCad CLI unavailable: {cli}")
            version_argv = (executable, "version")
            convert_argv = (executable, "pcb", "import", "--format", input_format,
                            "--output", str(board), "--report-format", "json",
                            "--report-file", str(native_report), str(source))
        else:
            image = pinned_image(record.image)
            prefix = docker_prefix()
            version_argv = (*prefix, image, "version")
            user_source = f"/input/{source.name}"
            mounts = ("-v", f"{source.parent}:/input:ro",
                      "-v", f"{journal.directory}:/output:rw", "-w", "/input")
            convert_argv = (*prefix, *mounts, image, "pcb", "import", "--format", input_format,
                            "--output", f"/output/stage/{board.name}", "--report-format", "json",
                            "--report-file", "/output/kicad-import-report.json", user_source)
        with journal.stage("version"):
            commands["version"] = run_command(root, version_argv, timeout=600)
            journal.save_model("version-command", commands["version"])
            if commands["version"].returncode != 0 or commands["version"].stdout.strip() != record.kicad_version:
                raise ValueError(f"Runner must be exact KiCad {record.kicad_version}; inspect version-command.json")
        with journal.stage("conversion"):
            commands["convert"] = run_command(root, convert_argv, timeout=600)
            journal.save_model("convert-command", commands["convert"])
            if commands["convert"].returncode != 0 or commands["convert"].error is not None:
                raise ValueError("KiCad import failed; inspect convert-command.json for stderr")
            if not board.is_file() or not board.read_bytes().lstrip().startswith(b"(kicad_pcb"):
                raise ValueError("KiCad reported success but produced no valid .kicad_pcb")
            if not native_report.is_file():
                raise ValueError("KiCad reported success but produced no JSON import report")
            native_summary = read_kicad_import_summary(native_report)
            if native_summary.errors:
                raise ValueError(f"KiCad import report contains {len(native_summary.errors)} errors; "
                                 "inspect kicad-import-report.json")
            board_hash = _digest(board)
            if _digest(source) != source_hash:
                raise ValueError("Foreign source changed during conversion; discard this receipt")
            native_project.write_text("{}\n", encoding="utf-8")
        with journal.stage("native-import-preview"):
            preview = import_project(root, native_project, project_id, toolchain_id, dry_run=True)
            journal.save_model("import-preview", preview)
            if preview.status != "PASS":
                raise ValueError(f"Native import preview failed: {preview.issues}")
        next_command = ("python -B -m kicad_tooling.template import-project --source "
                        f"{shlex.quote(str(native_project))} --project-id {shlex.quote(project_id)} "
                        f"--toolchain {shlex.quote(toolchain_id)} --format text")
        actions = (("Open stage/*.kicad_pcb with the exact KiCad version and inspect layer mapping, "
                    "net names, footprint links, geometry, and kicad-import-report.json."),
                   ("Only after engineering review, run the import command. The result is pcb_only "
                    "and cannot establish schematic or release coverage."))
        status = "PASS"
    except (OSError, ValueError, StopIteration) as exc:
        error = f"{type(exc).__name__}: {exc}"
        actions = (("Inspect events.log, doctor.json, convert-command.json and the raw KiCad report "
                    "where present; repair the source or runner, then rerun into a fresh receipt."),)
        journal.event("conversion", "FAIL", error)
    report = ForeignPcbReport(
        status=status, project_id=project_id, toolchain_id=toolchain_id,
        input_format=input_format, source_file=str(source), source_sha256=source_hash,
        run_directory=str(journal.directory), runner=selected, commands=commands,
        native_summary=native_summary,
        board_sha256=board_hash, import_preview=preview, next_command=next_command,
        next_actions=actions, error=error,
    )
    journal.finish_named("conversion", report, render_text(report), report.status)
    return report
