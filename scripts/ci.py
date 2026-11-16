"""Run package checks and an installed-wheel rehearsal with retained logs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import venv
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from kicad_tooling.ci_module_size_preflight import (
    MODULE_SIZE_TEST_PATH,
    module_size_preflight_command,
)
from kicad_tooling.ci_template_playtest import verify_adapted_project
from kicad_tooling.ci_typecheck import pyright_command, validate_typecheck_paths
from kicad_tooling.package_build import build_distributions
from kicad_tooling.platforms import is_windows_host
from kicad_tooling.pytest_metrics import report_pytest_metrics
from kicad_tooling.pytest_scope import pytest_selection_arguments, validate_test_module_files

ROOT = Path(__file__).resolve().parents[1]


def stage(
    name: str,
    command: tuple[str, ...],
    output: Path,
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    started = time.monotonic()
    print(f"tooling-ci: {name} started", flush=True)
    result = subprocess.run(
        command, cwd=cwd, env=environment, capture_output=True, text=True, check=False
    )
    (output / f"{name}.stdout.log").write_text(result.stdout, encoding="utf-8")
    (output / f"{name}.stderr.log").write_text(result.stderr, encoding="utf-8")
    status = "PASS" if result.returncode == 0 else "FAIL"
    entry: dict[str, object] = {
        "time_utc": datetime.now(UTC).isoformat(),
        "stage": name,
        "status": status,
        "exit_code": result.returncode,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "command": list(command),
    }
    if name == "unit":
        entry["pytest_metrics"] = report_pytest_metrics(result.stdout)
    with (output / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, sort_keys=True) + "\n")
    print(f"tooling-ci: {name} {status.lower()} ({entry['elapsed_seconds']}s)", flush=True)
    if result.returncode:
        print(result.stdout[-3000:], file=sys.stderr)
        print(result.stderr[-3000:], file=sys.stderr)
        raise RuntimeError(f"{name} failed; inspect {output}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Optional separate populated template checkout for integration",
    )
    parser.add_argument(
        "--build-python",
        default=sys.executable,
        help="Python with build, setuptools and setuptools-scm for packaging",
    )
    parser.add_argument(
        "--skip-mdrepo",
        action="store_true",
        help="Offline local rehearsal only; hosted CI must run mdrepo",
    )
    parser.add_argument(
        "--pytest-markexpr",
        help="Optional pytest marker expression for a scoped prerelease lint gate",
    )
    parser.add_argument(
        "--pytest-paths",
        nargs="+",
        help="Optional explicit test modules to combine with --pytest-markexpr selection",
    )
    parser.add_argument(
        "--typecheck-paths",
        nargs="+",
        help="Optional catalog-selected Python modules for the prerelease Pyright stages",
    )
    args = parser.parse_args()
    try:
        pytest_paths = validate_test_module_files(args.pytest_paths or (), ROOT)
        typecheck_paths = validate_typecheck_paths(args.typecheck_paths or (), ROOT)
    except ValueError as error:
        parser.error(str(error))
    logs = ROOT / "build/ci"
    logs.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="run-", dir=logs))
    try:
        if args.project_root is not None:
            os.environ["KICAD_TEMPLATE_ROOT"] = str(args.project_root.resolve())
        origin = stage(
            "development-install",
            (sys.executable, "-I", "-c", "import kicad_tooling; print(kicad_tooling.__file__)"),
            output,
            cwd=output,
        )
        if Path(origin.stdout.strip()).resolve() != (ROOT / "kicad_tooling/__init__.py").resolve():
            raise RuntimeError(
                "Install this checkout with python -m pip install -e "
                "'.[dev,fabrication_connectivity]' "
                "before running its regression suite"
            )
        stage(
            "ruff-format",
            (
                sys.executable,
                "-I",
                "-m",
                "ruff",
                "format",
                "--check",
                "kicad_tooling",
                "tests",
                "scripts",
            ),
            output,
            cwd=ROOT,
        )
        stage(
            "ruff",
            (
                sys.executable,
                "-I",
                "-m",
                "ruff",
                "check",
                "--no-cache",
                "kicad_tooling",
                "tests",
                "scripts",
            ),
            output,
            cwd=ROOT,
        )
        stage(
            "alphus-module-role-boundaries",
            (
                sys.executable,
                "-I",
                "-m",
                "alphus",
                "--root",
                str(ROOT),
                "--config",
                "quality-gates.toml",
                "--profile",
                "module-role-boundaries",
                "--json",
            ),
            output,
            cwd=ROOT,
        )
        stage(
            "alphus-shared-utility-duplication",
            (
                sys.executable,
                "-I",
                "-m",
                "alphus",
                "--root",
                str(ROOT),
                "--config",
                "quality-gates.toml",
                "--profile",
                "shared-utility-duplication",
                "--json",
            ),
            output,
            cwd=ROOT,
        )
        stage(
            "rumdl",
            (
                sys.executable,
                "-I",
                "-m",
                "kicad_tooling.markdown_check",
                "check",
                ".",
                "--no-cache",
            ),
            output,
            cwd=ROOT,
        )
        if not args.skip_mdrepo:
            stage("mdrepo", (sys.executable, "-m", "mdrepo", "check", "."), output, cwd=ROOT)
        unit_environment = os.environ.copy()
        unit_environment.pop("KICAD_RUN_NATIVE_SCHEMATIC_GEOMETRY", None)
        unit_environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        stage(
            "module-size-preflight",
            module_size_preflight_command(sys.executable),
            output,
            cwd=ROOT,
            environment=unit_environment,
        )
        unit_command = (
            sys.executable,
            "-B",
            "-I",
            "-m",
            "pytest",
            "-q",
            "--durations=10",
        )
        unit_command += pytest_selection_arguments(pytest_paths, args.pytest_markexpr)
        if MODULE_SIZE_TEST_PATH not in pytest_paths:
            unit_command += ("--ignore", MODULE_SIZE_TEST_PATH)
        stage(
            "unit",
            unit_command,
            output,
            cwd=ROOT,
            environment=unit_environment,
        )
        if os.environ.get("KICAD_RUN_NATIVE_SCHEMATIC_GEOMETRY") == "1":
            from kicad_tooling.hwrepo.native_geometry_lane import run

            run(ROOT, output, stage)
        stage(
            "pyright",
            pyright_command(sys.executable, target_paths=typecheck_paths),
            output,
            cwd=ROOT,
        )
        stage(
            "windows-types",
            pyright_command(sys.executable, target_paths=typecheck_paths, windows=True),
            output,
            cwd=ROOT,
        )
        rebuilt_wheel, version = build_distributions(ROOT, output, args.build_python, stage)
        environment_dir = output / "environment"
        venv.EnvBuilder(with_pip=True).create(environment_dir)
        python = environment_dir / ("Scripts/python.exe" if is_windows_host() else "bin/python")
        command = environment_dir / (
            "Scripts/kicad-team.exe" if is_windows_host() else "bin/kicad-team"
        )
        install = [str(python), "-m", "pip", "install", "--no-cache-dir"]
        stage(
            "install",
            (*install, f"{rebuilt_wheel}[project,mcp,fabrication_connectivity]"),
            output,
            cwd=output,
        )
        external = os.environ.copy()
        external.pop("PYTHONPATH", None)
        origin = stage(
            "installed-origin",
            (str(python), "-I", "-c", "import kicad_tooling; print(kicad_tooling.__file__)"),
            output,
            cwd=output,
            environment=external,
        )
        if not Path(origin.stdout.strip()).resolve().is_relative_to(environment_dir.resolve()):
            raise RuntimeError("Rehearsal imported tooling outside the installed wheel environment")
        installed_version = stage(
            "installed-version",
            (str(command), "--version"),
            output,
            cwd=output,
            environment=external,
        )
        if installed_version.stdout.strip() != f"kicad-team-tooling {version}":
            raise RuntimeError("Installed command reported an unexpected package version")
        project = args.project_root.resolve() if args.project_root else None
        if project is not None:
            inventory = stage(
                "external-inventory",
                (str(command), "template", "list", "--root", str(project), "--format", "json"),
                output,
                cwd=output,
                environment=external,
            )
            if json.loads(inventory.stdout)["status"] != "PASS":
                raise RuntimeError("External inventory did not pass")
            surface = stage(
                "external-surface",
                (str(command), "surface", "--root", str(project), "--format", "json"),
                output,
                cwd=output,
                environment=external,
            )
            if json.loads(surface.stdout)["status"] != "PASS":
                raise RuntimeError("External CLI/MCP declaration parity did not pass")
            if (project / "examples/projects/controller/project.json").is_file():
                stage(
                    "external-verify",
                    (
                        str(command),
                        "verify",
                        "--root",
                        str(project),
                        "--project",
                        "controller",
                        "--format",
                        "json",
                    ),
                    output,
                    cwd=output,
                    environment=external,
                )
                verify_adapted_project(project, command, output, external, stage)
                stage(
                    "external-playtest",
                    (
                        str(python),
                        "-B",
                        str(ROOT / "scripts/playtest.py"),
                        "--template",
                        str(project),
                        "--output",
                        str(output / "playtest"),
                    ),
                    output,
                    cwd=output,
                    environment=external,
                )
        print(f"tooling-ci: logs {output}")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"tooling-ci: {exc}; logs {output}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
