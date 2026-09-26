"""Project-focused, source-bound KiCad 3D previews and exchange exports."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from ..check_toolchain import cli_executable
from ..validate import hashes
from .contracts import repo_path
from .diagnostic_journal import DiagnosticJournal
from .discovery import load_config, load_registry
from .doctor import NativeRunner, doctor
from .model_inventory import inspect_models
from .models import (
    DEFAULT_THREE_D_VIEWS,
    THREE_D_VIEWS,
    CommandEvidence,
    ExportMode,
    ExportStatus,
    ModelInventoryReport,
    ProjectConfig,
    ProjectKind,
    SelectedRunner,
    ThreeDReport,
    ThreeDView,
)

# Preserve the original service-module import surface for existing consumers.
__all__ = [
    "ExportMode",
    "ExportStatus",
    "ModelInventoryReport",
    "SelectedRunner",
    "ThreeDReport",
    "ThreeDView",
    "generate",
    "render_text",
    "selected_views",
]


def _command(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
    started = datetime.now(UTC).isoformat()
    try:
        result = subprocess.run(
            argv, cwd=root, capture_output=True, text=True, timeout=timeout, check=False,
        )
        return CommandEvidence(
            argv=argv, started_utc=started, returncode=result.returncode,
            stdout=result.stdout, stderr=result.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout or ""
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr or ""
        return CommandEvidence(
            argv=argv, started_utc=started, returncode=124, stdout=stdout, stderr=stderr,
            error=f"3D command timed out after {timeout} seconds",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return CommandEvidence(argv=argv, started_utc=started, returncode=127, error=str(exc))


def _container_prefix(root: Path, output: Path, config: ProjectConfig) -> tuple[str, ...]:
    if re.fullmatch(r"[^@\s]+@sha256:[a-f0-9]{64}", config.image) is None:
        raise ValueError("Project KiCad image is not digest-pinned")
    user: tuple[str, ...] = () if sys.platform == "win32" else (
        "--user", f"{os.getuid()}:{os.getgid()}",
    )
    return (
        "docker", "run", "--rm", "--platform", "linux/amd64", *user,
        "--entrypoint", "kicad-cli", "-e", "HOME=/tmp/kicad-3d",
        "-v", f"{os.fspath(root)}:/work:ro", "-v", f"{os.fspath(output)}:/output:rw",
        "-w", "/work", config.image,
    )


def _run_kicad(
    root: Path, output: Path, config: ProjectConfig, selected: Literal["local", "container"],
    cli: str, args: tuple[str, ...], timeout: int = 300,
) -> CommandEvidence:
    if selected == "container":
        return _command(root, (*_container_prefix(root, output, config), *args), timeout)
    executable = cli_executable(cli)
    if executable is None:
        raise ValueError(f"Exact local KiCad CLI is unavailable: {cli}")
    local_args = tuple(
        str(output / value.removeprefix("/output/")) if value.startswith("/output/")
        else str(root / value.removeprefix("/work/")) if value.startswith("/work/")
        else value
        for value in args
    )
    return _command(root, (executable, *local_args), timeout)


def _valid_artifact(path: Path, kind: str) -> bool:
    if not path.is_file() or path.stat().st_size < 16:
        return False
    with path.open("rb") as stream:
        header = stream.read(32)
    if kind == "png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if kind == "glb":
        return header.startswith(b"glTF\x02\x00\x00\x00")
    return header.startswith(b"ISO-10303-21") if kind == "step" else False


def _selected(root: Path, project_id: str) -> tuple[ProjectConfig, str]:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", project_id) is None:
        raise ValueError("Project ID must use letters, digits, periods, underscores or hyphens")
    record = next((item for item in load_registry(root).projects if item.id == project_id), None)
    if record is None:
        raise ValueError(f"Unknown project {project_id!r}; run kicad_tooling.template list")
    if record.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        raise ValueError(f"Project {project_id} is {record.kind.value}; 3D views require a PCB")
    config = load_config(root, record.config)
    derived = repo_path(root, config.project).with_suffix(".kicad_pcb")
    board = repo_path(root, derived.relative_to(root).as_posix())
    if not board.is_file():
        raise ValueError(f"Project {project_id} has no PCB source: {board.relative_to(root)}")
    return config, board.relative_to(root).as_posix()


def _source_hashes(root: Path, config: ProjectConfig) -> dict[str, str]:
    actual = hashes(root, config.source_roots)
    expected = set(config.required_inputs)
    if set(actual) != expected:
        missing, extra = sorted(expected - set(actual)), sorted(set(actual) - expected)
        raise ValueError(
            f"Project source inventory differs from project.json; missing={missing}, unlisted={extra}. "
            "Declare reviewed model/source files before making a 3D preview."
        )
    return actual


def selected_views(views: Iterable[str] | None = None) -> tuple[ThreeDView, ...]:
    """Resolve the default camera bundle or validate an explicitly selected view list."""
    selected = DEFAULT_THREE_D_VIEWS if views is None else tuple(views)
    if not selected:
        raise ValueError("Select at least one 3D view")
    if len(set(selected)) != len(selected):
        raise ValueError("3D views must be unique")
    unknown = sorted(set(selected) - set(THREE_D_VIEWS))
    if unknown:
        raise ValueError("Unknown 3D view(s): " + ", ".join(unknown))
    return selected  # type: ignore[return-value]


def _specifications(
    board: str, assembly_variant: str | None = None,
    views: Iterable[str] | None = None,
) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    source = f"/work/{board}"
    variant = ("--variant", assembly_variant) if assembly_variant else ()
    side_views: dict[ThreeDView, str] = {
        "top": "top", "bottom": "bottom", "left": "left", "right": "right",
        "front": "front", "back": "back",
    }
    rotations = {
        "angled": "45,0,0", "angled-90": "45,0,90",
        "angled-180": "45,0,180", "angled-270": "45,0,270",
    }
    specifications: list[tuple[str, str, tuple[str, ...]]] = []
    for name in selected_views(views):
        filename = f"{name}.png"
        args: tuple[str, ...] = (
            "pcb", "render", "-o", f"/output/{filename}", "--width", "1600",
            "--height", "1600" if name in rotations else "900",
            "--side", side_views.get(name, "top"),
        )
        if name in rotations:
            # KiCad frames the unrotated board before applying camera rotation.
            # Square framing plus a margin accommodates the quarter-turn views.
            args += ("--rotate", rotations[name], "--perspective", "--zoom", "0.6")
        specifications.append((name, filename, (*args, *variant, source)))
    specifications.extend((
        ("step", "board.step", ("pcb", "export", "step", "--subst-models", "--no-dnp",
                                  *variant, "-o", "/output/board.step", source)),
        ("glb", "board.glb", ("pcb", "export", "glb", "--subst-models", "--no-dnp",
                                *variant, "-o", "/output/board.glb", source)),
    ))
    return tuple(specifications)


def render_text(report: ThreeDReport, detail: Literal["brief", "full"] = "brief") -> str:
    lines = [
        f"3D workflow: {report.status}", f"Project: {report.project_id}",
        f"Mode: {report.mode}", f"Model coverage: {report.models.status if report.models else 'NOT_RUN'}",
        f"Runner: {report.runner}", f"Receipt: {report.run_directory}",
    ]
    if report.assembly_variant:
        lines.append(f"KiCad assembly variant: {report.assembly_variant}")
    if report.models is not None:
        lines.append(f"Footprints: {len(report.models.footprints)}")
        selected_findings = (report.models.findings if detail == "full"
                             else report.models.findings[:5])
        for finding in selected_findings:
            lines.append(f"  {finding.code} at {finding.location}: {finding.observed}")
            lines.append(f"    Fix: {finding.action}")
        if detail == "brief" and len(report.models.findings) > 5:
            lines.append("  More model findings: --detail full or models.json")
        candidates = tuple(
            item for item in report.models.footprints
            if not item.models and item.candidate_assets
        )
        for footprint in (candidates if detail == "full" else candidates[:5]):
            lines.append(
                f"  Candidate for {footprint.reference} (verify package): "
                + ", ".join(footprint.candidate_assets)
            )
        if detail == "brief" and len(candidates) > 5:
            lines.append("  More candidate assets: --detail full or models.json")
    for name in report.artifacts_sha256:
        lines.append(f"Output: {Path(report.run_directory) / name}")
    if report.error:
        label = "Tool error" if report.status == "ERROR" else "Finding"
        lines.append(f"{label}: {report.error}")
    for action in report.next_actions:
        lines.append(f"Next: {action}")
    return "\n".join(lines)


def generate(
    root: Path, project_id: str, *, check_models: bool = False,
    runner: NativeRunner = "auto", cli: str = "kicad-cli", output: Path | None = None,
    assembly_variant: str | None = None,
    views: Iterable[str] | None = None,
    detail: Literal["brief", "full"] = "brief",
) -> ThreeDReport:
    """Inspect one PCB or export selected standard camera views and geometry."""
    root = root.resolve()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", project_id) is None:
        raise ValueError("Project ID must use letters, digits, periods, underscores or hyphens")
    if assembly_variant is not None and not assembly_variant.strip():
        raise ValueError("KiCad assembly variant cannot be blank")
    repo_path(root, "build/diagnostics")
    if output is not None:
        output = root / output if not output.is_absolute() else output
        if not output.is_relative_to(root / "build"):
            raise ValueError("3D output must be under this repository's ignored build/")
        output = repo_path(root, output.relative_to(root).as_posix())
    journal = DiagnosticJournal(root, project_id, output, label="visualize")
    mode: ExportMode = "inspect" if check_models else "generate"
    status: ExportStatus = "FAIL"
    selected_runner: SelectedRunner = "none"
    config: ProjectConfig | None = None
    board: str | None = None
    inventory: ModelInventoryReport | None = None
    source: dict[str, str] = {}
    commands: dict[str, CommandEvidence] = {}
    artifacts: dict[str, str] = {}
    actions: tuple[str, ...] = ()
    error: str | None = None
    try:
        with journal.stage("project-selection"):
            config, board = _selected(root, project_id)
            resolved_views = selected_views(views)
            if assembly_variant:
                from .exports import require_declared_variant

                require_declared_variant(repo_path(root, config.project), assembly_variant)
        with journal.stage("model-inventory"):
            inventory = inspect_models(root, config)
            journal.save_model("models", inventory)
        if inventory.status == "FAIL":
            actions = ("Repair the broken 3D model references in models.json, then rerun.",)
        else:
            with journal.stage("project-source"):
                source = _source_hashes(root, config)
        if inventory.status != "FAIL" and check_models:
            status = "PASS"
            if inventory.status == "REVIEW":
                actions = ("Review unassigned footprints in models.json; add approved 3D models where needed.",)
        elif inventory.status != "FAIL":
            with journal.stage("runner-readiness"):
                ready = doctor(root, native=True, toolchain_id=config.toolchain_id,
                               cli=cli, project_id=project_id, runner=runner)
                journal.save_model("doctor", ready)
            if ready.status != "PASS":
                actions = ready.next_actions + (
                    "Use kicad_tooling.template doctor --native --project-id " + project_id
                    + " to repair the 3D runner.",
                )
            else:
                choice = next(
                    check.observed for check in ready.checks if check.id == "native-runner"
                )
                if choice not in {"local", "container"}:
                    raise ValueError(f"Doctor selected an unknown native runner: {choice!r}")
                selected_runner = "local" if choice == "local" else "container"
                with journal.stage("version"):
                    version = _run_kicad(root, journal.directory, config, selected_runner,
                                         cli, ("version",))
                    commands["version"] = version
                    journal.save_model("version-command", version)
                if version.returncode != 0 or version.stdout.strip() != config.kicad_version:
                    actions = (
                        f"Use exact KiCad {config.kicad_version}; inspect version-command.json.",
                    )
                else:
                    for name, filename, args in _specifications(
                        board, assembly_variant, resolved_views,
                    ):
                        with journal.stage(name):
                            result = _run_kicad(root, journal.directory, config, selected_runner,
                                                cli, args, timeout=600)
                            commands[name] = result
                            journal.save_model(f"{name}-command", result)
                        if result.returncode != 0 or result.error is not None:
                            actions = (
                                f"Open {name}-command.json for KiCad stderr; repair the source or "
                                + "runner, then rerun into a fresh receipt.",
                            )
                            break
                        kind = "png" if filename.endswith(".png") else filename.rsplit(".", 1)[1]
                        path = journal.directory / filename
                        if not _valid_artifact(path, kind):
                            actions = (
                                f"KiCad reported success but {filename} is missing or invalid. "
                                + f"Inspect {name}-command.json and report a tooling defect.",
                            )
                            break
                        artifacts[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
                    else:
                        status = "PASS"
                        if inventory.status == "REVIEW":
                            actions = (
                                "Review unassigned footprints in models.json; these outputs may show a bare PCB.",
                                "Inspect PNG and exchange geometry before using them for mechanical decisions.",
                            )
                        else:
                            actions = ("Inspect PNG and exchange geometry before mechanical approval.",)
        if status == "PASS":
            with journal.stage("source-unchanged"):
                if _source_hashes(root, config) != source:
                    raise ValueError(
                        "Project source changed while the 3D receipt was being generated; "
                        "discard this receipt and rerun from a stable source snapshot"
                    )
    except KeyboardInterrupt as exc:
        journal.fail(exc)
        raise
    except (OSError, ValueError) as exc:
        status = "FAIL"
        error = f"{type(exc).__name__}: {exc}"
        journal.event("input", "FAIL", error)
        actions = (
            "Repair the selected project source, manifest or 3D model inputs, then rerun "
            "into a fresh receipt. Use kicad_tooling.template diagnose --project-id " + project_id
            + " for the broader repair queue.",
        )
    except Exception as exc:  # noqa: BLE001 - retain a complete receipt on tooling faults
        journal.fail(exc)
        status = "ERROR"
        error = f"{type(exc).__name__}: {exc}"
        actions = (
            f"Inspect {journal.directory / 'events.log'} and "
            + f"{journal.directory / 'error.txt'}; repair the input or report a tool defect.",
        )
    report = ThreeDReport(
        project_id=project_id, mode=mode, status=status,
        run_directory=str(journal.directory),
        toolchain_id=None if config is None else config.toolchain_id,
        kicad_version=None if config is None else config.kicad_version,
        runner=selected_runner, assembly_variant=assembly_variant,
        board=board, source_sha256=source,
        models=inventory, commands=commands, artifacts_sha256=artifacts,
        next_actions=actions, error=error,
    )
    human = render_text(report, detail)
    if status == "ERROR":
        journal.save_model("visualization", report)
        (journal.directory / "visualization.txt").write_text(human + "\n", encoding="utf-8")
    else:
        journal.finish_named("visualization", report, human, status)
    return report
