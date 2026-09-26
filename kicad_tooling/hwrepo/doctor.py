"""Read-only environment diagnostics for adopting and checking the template."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import Literal

from kicad_tooling import package_version
from kicad_tooling.check_toolchain import assessment, observed_version, toolchain

from .discovery import load_config, load_registry
from .kicad_compatibility import require_cli_profile
from .models import EnvironmentCheck, TemplateDoctorReport
from .template import preflight

MINIMUM_PYTHON = (3, 11)
NativeRunner = Literal["auto", "local", "container"]
IMAGE_DIGEST = re.compile(r".+@sha256:[a-f0-9]{64}\Z")


def command_output(argv: tuple[str, ...]) -> str | None:
    """Return concise successful command output without exposing interactive prompts."""
    try:
        result = subprocess.run(
            argv, text=True, capture_output=True, check=False, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = result.stdout.strip() or result.stderr.strip()
    return output.splitlines()[0] if result.returncode == 0 and output else None


def environment_check(
    identifier: str,
    required: bool,
    expected: str,
    observed: str | None,
    success: bool,
    success_action: str,
    failure_action: str,
) -> EnvironmentCheck:
    """Create one stable diagnostic row with required/optional failure semantics."""
    status = "PASS" if success else ("FAIL" if required else "OPTIONAL")
    return EnvironmentCheck(
        id=identifier,
        required=required,
        status=status,
        expected=expected,
        observed=observed,
        next_action=success_action if success else failure_action,
    )


def doctor(
    root: Path,
    native: bool = False,
    toolchain_id: str | None = None,
    cli: str = "kicad-cli",
    project_id: str | None = None,
    runner: NativeRunner = "auto",
    electrical: bool = False,
    ngspice: str = "ngspice",
) -> TemplateDoctorReport:
    """Inspect prerequisites for the same project runner selected by kicad_tooling.verify."""
    native = native or electrical
    resolved = root.resolve()
    checks: list[EnvironmentCheck] = []
    if runner not in {"auto", "local", "container"}:
        raise ValueError(f"Unknown native runner: {runner}")
    if not native and runner != "auto":
        raise ValueError("--runner requires native doctor checks")

    python_version = ".".join(str(value) for value in sys.version_info[:3])
    python_ok = sys.version_info[:2] >= MINIMUM_PYTHON
    checks.append(environment_check(
        "python", True, "Python 3.11 or newer", python_version, python_ok,
        "Python can run the supported tooling package.",
        "Install Python 3.11 or newer, recreate the virtual environment, and install requirements-tooling.txt.",
    ))

    try:
        installed = package_version()
    except PackageNotFoundError:
        installed = None
    checks.append(environment_check(
        "tooling-package", True, "Installed kicad-team-tooling distribution", installed,
        installed is not None, "Shared tooling is installed independently of project source.",
        "Activate the project environment and install requirements-tooling.txt.",
    ))

    git_path = shutil.which("git")
    git_version = None if git_path is None else command_output((git_path, "--version"))
    checks.append(environment_check(
        "git", True, "Git available on PATH", git_version, git_version is not None,
        "Git is available for source and release provenance.",
        "Install Git and make it available on PATH.",
    ))
    git_repository = None if git_path is None else command_output(
        (
            git_path,
            "-c",
            f"safe.directory={resolved.as_posix()}",
            "-C",
            str(resolved),
            "rev-parse",
            "--is-inside-work-tree",
        )
    )
    checks.append(environment_check(
        "git-repository", True, "Repository is inside a Git worktree", git_repository,
        git_repository == "true", "The repository can record source provenance.",
        "Initialize or clone the Git repository before using the guided adoption command.",
    ))

    template = preflight(resolved)
    checks.append(environment_check(
        "template", True, "Complete template contract", template.template_version,
        template.status == "PASS", "The template contract is complete.",
        "Run kicad_tooling.template preflight and repair the reported missing or invalid template input.",
    ))

    docker_path = shutil.which("docker") if runner != "local" or not native else None
    docker_version = None if docker_path is None else command_output(
        (docker_path, "version", "--format", "{{.Server.Version}}")
    )

    selected_toolchain = toolchain_id
    if native and project_id is None and toolchain_id is None:
        checks.append(environment_check(
            "native-target", True, "Registered project ID or toolchain ID", None,
            False, "The exact native target is selected.",
            "Rerun doctor with --project-id <id> for the board you intend to verify.",
        ))
    project_ok = project_id is None
    if project_id is not None:
        try:
            registry = load_registry(resolved)
            project = next(item for item in registry.projects if item.id == project_id)
            config = load_config(resolved, project.config)
            if toolchain_id is not None and toolchain_id != config.toolchain_id:
                raise ValueError(
                    f"Project {project_id} uses {config.toolchain_id}, not {toolchain_id}"
                )
            selected_toolchain = config.toolchain_id
            project_ok = True
            checks.append(environment_check(
                "project", True, f"Registered project {project_id}", project.config,
                True, "The selected project has a catalogued toolchain.",
                "Select a registered project ID from catalog/projects.json.",
            ))
        except (OSError, ValueError, StopIteration) as exc:
            checks.append(environment_check(
                "project", True, f"Registered project {project_id}", str(exc),
                False, "The selected project has a catalogued toolchain.",
                "Repair project discovery or select a registered project ID, then rerun doctor.",
            ))

    local_version: str | None = None
    local_ok = False
    image_ok = False
    profile_ok = False
    expected_local = "Optional exact local KiCad CLI"
    if selected_toolchain is not None:
        try:
            record = toolchain(resolved, selected_toolchain)
            checks.append(environment_check(
                "toolchain", True, f"One catalogued {selected_toolchain} record", record.kicad_version,
                True, "The selected toolchain is catalogued.",
                "Select a toolchain ID from catalog/toolchains.json.",
            ))
            expected_local = f"KiCad {record.kicad_version} for {selected_toolchain}"
            if native:
                try:
                    profile = require_cli_profile(record)
                    profile_ok = True
                    profile_action = (
                        "The CLI/report adapter is selected; an explicit profile is an author "
                        "compatibility declaration, not tested-version certification. Run native "
                        "acceptance for the exact catalogued version before adoption."
                    )
                except ValueError as exc:
                    profile = None
                    profile_action = str(exc)
                checks.append(environment_check(
                    "cli-profile", True, "Supported KiCad CLI/report compatibility profile",
                    profile, profile_ok, profile_action, profile_action,
                ))
            image_ok = IMAGE_DIGEST.fullmatch(record.image) is not None
            if runner != "container" or not native:
                try:
                    local_version = observed_version(cli)
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    local_version = f"probe failed: {exc}"
                local_ok = assessment(record, local_version).status == "PASS"
            if native:
                checks.append(environment_check(
                    "native-image", True, "Digest-pinned catalogued KiCad image",
                    record.image, image_ok,
                    "The project image is pinned by digest.",
                    "Pin the selected image in catalog/toolchains.json by sha256 digest.",
                ))
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            checks.append(environment_check(
                "toolchain", True, f"One catalogued {selected_toolchain} record", str(exc),
                False, "The selected toolchain is catalogued.",
                "Select a toolchain ID from catalog/toolchains.json.",
            ))

    container_ok = docker_version is not None and (image_ok if selected_toolchain is not None else True)
    selected_runner: Literal["local", "container"] | None = None
    if runner != "container" and local_ok:
        selected_runner = "local"
    elif runner != "local" and container_ok:
        selected_runner = "container"
    if not project_ok or (native and not profile_ok):
        selected_runner = None
    native_ok = selected_runner is not None
    checks.append(environment_check(
        "docker", False, "Running Docker daemon for digest-pinned native checks",
        docker_version, docker_version is not None,
        "Docker can run a digest-pinned KiCad image when one is selected.",
        "Start Docker, or use an exact installed KiCad CLI with --runner local.",
    ))
    checks.append(environment_check(
        "kicad-cli", False, expected_local, local_version, local_ok,
        "The installed KiCad CLI matches the selected toolchain.",
        "Install the selected exact KiCad version, or use --runner container with Docker.",
    ))
    if native:
        next_verify = (
            "python -B -m kicad_tooling.verify --project "
            + (project_id or "<id>")
            + " --depth native"
        )
        checks.append(environment_check(
            "native-runner", True,
            f"{runner}: exact local KiCad or running Docker with pinned image",
            selected_runner,
            native_ok, f"kicad_tooling.verify can use the {selected_runner} runner." if native_ok else
            "Select a registered project and start Docker or install its exact KiCad CLI.",
            "Start Docker for --runner container, or install this project's exact KiCad CLI "
            + f"and use --runner local. Then run {next_verify}.",
        ))

    if electrical:
        from .electrical_doctor import electrical_checks

        checks.extend(electrical_checks(resolved, project_id, ngspice))

    failed = tuple(check for check in checks if check.status == "FAIL")
    return TemplateDoctorReport(
        native_requested=native, electrical_requested=electrical,
        checks=tuple(checks),
        status="FAIL" if failed else "PASS",
        next_actions=tuple(dict.fromkeys(check.next_action for check in failed)),
    )
