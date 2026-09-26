"""Verify a project: portable policy, native KiCad, or native plus electrical simulations."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from .check_all import check_all
from .ci import project_static_pipeline
from .hwrepo.container_git import git_metadata_mounts
from .hwrepo.contracts import read_model
from .hwrepo.diagnostic_journal import DiagnosticJournal
from .hwrepo.diagnostics import diagnose_project, format_text
from .hwrepo.discovery import load_config, load_registry
from .hwrepo.doctor import NativeRunner, doctor
from .hwrepo.models import (
    CheckAllSummary,
    CommandEvidence,
    DiagnosticReport,
    ProjectStaticPipelineReport,
    ProjectVerificationReport,
)
from .hwrepo.selection import ProjectSelector, resolve_project_ids

Depth = Literal["portable", "native", "electrical"]


class SelectionFailure(Exception):
    """A user-selected project cannot be discovered from the repository contract."""


def run_command(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
    """Capture the complete subprocess result, including startup and timeout failures."""
    started = datetime.now(UTC).isoformat()
    try:
        completed = subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:

        def output(value: bytes | str | None) -> str:
            return (
                value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
            )

        return CommandEvidence(
            argv=argv,
            started_utc=started,
            returncode=124,
            stdout=output(exc.stdout),
            stderr=output(exc.stderr),
            error=f"Runner timed out after {timeout} seconds",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return CommandEvidence(argv=argv, started_utc=started, returncode=127, error=str(exc))
    return CommandEvidence(
        argv=argv,
        started_utc=started,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def container_command(
    root: Path,
    image: str,
    project_id: str,
    dependencies: Path,
    native_output: Path,
) -> tuple[str, ...]:
    """Replay the hosted native command with only catalogued image and selected project."""
    deps = dependencies.relative_to(root).as_posix()
    output = native_output.relative_to(root).as_posix()
    command = ["docker", "run", "--rm", "--platform", "linux/amd64"]
    if sys.platform != "win32":
        command.extend(("--user", f"{os.getuid()}:{os.getgid()}"))
    command.extend(
        (
            "--entrypoint",
            f"/work/{deps}/bin/python",
            "-e",
            "HOME=/tmp/kicad-template",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "--mount",
            f"type=bind,source={root},target=/work",
            *git_metadata_mounts(root),
            "-w",
            "/work",
            image,
            "-I",
            "-B",
            "-m",
            "kicad_tooling.ci",
            "--kicad",
            "--project",
            project_id,
            "--output",
            output,
        )
    )
    return tuple(command)


def format_report(
    result: ProjectVerificationReport, detail: Literal["brief", "full"] = "brief"
) -> str:
    """Keep routine output short while retaining exact repair findings in the receipt."""
    lines = [
        f"Project verify: {result.status}",
        f"Project: {result.project_id}",
        f"Depth: {result.depth}",
        f"Portable: {result.portable.status if result.portable is not None else 'NOT_RUN'}",
    ]
    if result.depth in {"native", "electrical"}:
        lines.append(f"Runner: {result.runner}")
        lines.append(f"Native: {result.native.status if result.native is not None else 'NOT_RUN'}")
    lines.append(
        f"Electrical analysis: {result.electrical.status if result.electrical else 'NOT_RUN'}"
    )
    lines.append(f"Receipt: {result.run_directory}")
    if result.error:
        lines.append(f"Tool error: {result.error}")
    if result.diagnosis is not None:
        lines.append(format_text(result.diagnosis, detail))
    for action in result.next_actions:
        lines.append(f"Next: {action}")
    if result.status != "PASS":
        lines.append(
            "Full evidence: verification.json, events.log, and stage reports in the receipt."
        )
    return "\n".join(lines)


def verify(
    root: Path,
    project_id: str,
    depth: Depth = "portable",
    runner: NativeRunner = "auto",
    cli: str = "kicad-cli",
    output: Path | None = None,
    detail: Literal["brief", "full"] = "brief",
    ngspice: str = "ngspice",
) -> ProjectVerificationReport:
    """Run selected validation into a new ignored receipt and coach any failure."""
    root = root.resolve()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", project_id) is None:
        raise ValueError("Project ID must use letters, digits, periods, underscores or hyphens")
    if output is not None:
        output = (root / output).resolve() if not output.is_absolute() else output.resolve()
        if not output.is_relative_to(root / "build"):
            raise ValueError("Verification output must be under this repository's ignored build/")
    journal = DiagnosticJournal(root, project_id, output, label="verify")
    portable: ProjectStaticPipelineReport | None = None
    config = None
    native_doctor = None
    dependency_command = None
    native_command = None
    native = None
    electrical_report = None
    diagnosis: DiagnosticReport | None = None
    selected_runner: Literal["none", "local", "container"] = "none"
    next_actions: tuple[str, ...] = ()
    error: str | None = None
    status: Literal["PASS", "FAIL", "ERROR"] = "FAIL"

    def diagnose(native_report: Path | None = None) -> DiagnosticReport:
        result = diagnose_project(
            root,
            project_id,
            native_report,
            journal=journal,
            portable_report=portable,
        )
        result = result.model_copy(update={"run_directory": str(journal.directory)})
        journal.save_model("diagnosis", result)
        (journal.directory / "diagnosis.txt").write_text(
            format_text(result, detail) + "\n",
            encoding="utf-8",
        )
        return result

    try:
        with journal.stage("project-selection"):
            try:
                selected = resolve_project_ids(root, ProjectSelector(project_ids=(project_id,)))
                project = next(
                    item for item in load_registry(root).projects if item.id == selected[0]
                )
                config = load_config(root, project.config)
            except (OSError, ValueError, StopIteration) as exc:
                raise SelectionFailure(str(exc)) from exc
        with journal.stage("portable"):
            portable = project_static_pipeline(root, selected)
            journal.save_model("portable", portable)
        if portable.status != "PASS":
            diagnosis = diagnose()
            next_actions = (
                f"Fix the first blocking finding in {journal.directory / 'diagnosis.txt'}.",
            )
        elif depth == "portable":
            status = "PASS"
        else:
            with journal.stage("runner-readiness"):
                native_doctor = doctor(
                    root,
                    native=True,
                    toolchain_id=config.toolchain_id,
                    cli=cli,
                    project_id=project_id,
                    runner=runner,
                    electrical=depth == "electrical",
                    ngspice=ngspice,
                )
                journal.save_model("doctor", native_doctor)
            if native_doctor.status != "PASS":
                next_actions = native_doctor.next_actions
            else:
                choice = next(
                    check.observed for check in native_doctor.checks if check.id == "native-runner"
                )
                if choice == "local":
                    selected_runner = "local"
                elif choice == "container":
                    selected_runner = "container"
                else:
                    raise ValueError(f"Doctor selected an unknown runner: {choice!r}")
                native_output = journal.directory / "native"
                if choice == "local":
                    with journal.stage("native-local"):
                        native = check_all(root, native_output, cli, [project_id])
                else:
                    dependencies = journal.directory / "policy-deps"
                    dep_relative = dependencies.relative_to(root).as_posix()
                    with journal.stage("container-dependencies"):
                        dependency_command = run_command(
                            root,
                            (
                                sys.executable,
                                "-I",
                                "-B",
                                "-m",
                                "kicad_tooling.native_deps",
                                "--root",
                                str(root),
                                "--image",
                                config.image,
                                "--output",
                                dep_relative,
                            ),
                            600,
                        )
                        journal.save_model("dependency-command", dependency_command)
                    if dependency_command.returncode != 0:
                        next_actions = (
                            "Open dependency-command.json for the image probe or wheel-resolution "
                            + "error; start Docker, restore package access, then rerun into a fresh receipt.",
                        )
                    else:
                        with journal.stage("native-container"):
                            native_command = run_command(
                                root,
                                container_command(
                                    root,
                                    config.image,
                                    project_id,
                                    dependencies,
                                    native_output,
                                ),
                                900,
                            )
                            journal.save_model("native-command", native_command)
                        summary_path = native_output / "summary.json"
                        if summary_path.is_file():
                            native = read_model(summary_path, CheckAllSummary)
                        if native is None and native_command.returncode != 0:
                            next_actions = (
                                "Open native-command.json for Docker or KiCad stderr; verify the "
                                + "pinned image and Docker mount, then rerun into a fresh receipt.",
                            )
                        elif native is None:
                            next_actions = (
                                "The container returned success without native/summary.json. "
                                + "Inspect native-command.json and report this as a runner defect.",
                            )
                if native is not None:
                    journal.save_model("native", native)
                    if native.status == "FAIL":
                        project_summary = native_output / project_id / "summary.json"
                        if project_summary.is_file():
                            diagnosis = diagnose(project_summary)
                            next_actions = (
                                f"Fix the first native finding in {journal.directory / 'diagnosis.txt'} "
                                + "and rerun into a fresh receipt.",
                            )
                        else:
                            next_actions = (
                                f"Inspect {native_output / 'summary.json'} and the runner command; "
                                + "repair the preflight blocker before retrying.",
                            )
                    elif native_command is not None and native_command.returncode != 0:
                        next_actions = (
                            "The container returned a failure after writing a passing summary. "
                            + "Inspect native-command.json and retain this receipt for tool repair.",
                        )
                    else:
                        status = "PASS"
        if depth == "electrical" and status == "PASS":
            from .hwrepo.electrical_runner import analyze

            with journal.stage("electrical"):
                electrical_report = analyze(
                    root,
                    project_id,
                    journal.directory / "electrical",
                    journal.directory / "native" / project_id / "summary.json",
                    cli,
                    ngspice,
                )
                journal.save_model("electrical", electrical_report)
            if electrical_report.status != "PASS":
                status = "FAIL"
                next_actions = (
                    f"Resolve the electrical findings in {electrical_report.run_directory}.",
                )

    except SelectionFailure:
        diagnosis = diagnose()
        next_actions = (f"Repair the selection finding in {journal.directory / 'diagnosis.txt'}.",)
    except KeyboardInterrupt as exc:
        journal.fail(exc)
        raise
    except Exception as exc:  # noqa: BLE001 - retain a receipt for unexpected runner errors
        journal.fail(exc)
        status = "ERROR"
        error = f"{type(exc).__name__}: {exc}"
        next_actions = (
            f"Inspect {journal.directory / 'events.log'} and "
            + f"{journal.directory / 'error.txt'}; report a tool defect if inputs are valid.",
        )

    if (
        status == "PASS"
        and depth != "electrical"
        and config is not None
        and config.kind.value in {"pcb", "schematic"}
    ):
        next_actions += (
            "Full electrical analysis was not run at this depth. Review grounding, power and "
            "transient/frequency applicability with the electrical owner; "
            + (
                f"start with kicad-team electrical --project {project_id} --init, then "
                if config.electrical is None
                else ""
            )
            + f"run kicad-team verify --project {project_id} --depth electrical. "
            "Any configured static budgets or native grounding checks retain their separate results.",
        )

    result = ProjectVerificationReport(
        project_id=project_id,
        depth=depth,
        runner=selected_runner,
        run_directory=str(journal.directory),
        portable=portable,
        doctor=native_doctor,
        dependency_command=dependency_command,
        native_command=native_command,
        native=native,
        electrical=electrical_report,
        diagnosis=diagnosis,
        status=status,
        next_actions=next_actions,
        error=error,
    )
    human_text = format_report(result, detail)
    if status == "ERROR":
        journal.save_model("verification", result)
        (journal.directory / "verification.txt").write_text(human_text + "\n", encoding="utf-8")
    else:
        journal.finish_named("verification", result, human_text, status)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
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
    if args.depth == "portable" and args.runner != "auto":
        parser.error("--runner requires --depth native or electrical")
    if args.format == "json" and args.detail != "brief":
        parser.error("--detail is for text; JSON already includes every finding")
    try:
        result = verify(
            args.root,
            args.project,
            args.depth,
            args.runner,
            args.cli,
            args.output,
            args.detail,
            args.ngspice,
        )
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
