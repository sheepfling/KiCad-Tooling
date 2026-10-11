"""Run package checks and an installed-wheel rehearsal with retained logs."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import venv
from datetime import UTC, datetime
from pathlib import Path

from kicad_tooling.package_build import build_distributions

ROOT = Path(__file__).resolve().parents[1]


def stage(
    name: str,
    command: tuple[str, ...],
    output: Path,
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    started = time.monotonic()
    print(f"tooling-ci: {name} started", flush=True)
    result = subprocess.run(
        command, cwd=cwd, env=environment, capture_output=True, text=True, check=False
    )
    (output / f"{name}.stdout.log").write_text(result.stdout, encoding="utf-8")
    (output / f"{name}.stderr.log").write_text(result.stderr, encoding="utf-8")
    status = "PASS" if result.returncode == 0 else "FAIL"
    entry = {
        "time_utc": datetime.now(UTC).isoformat(),
        "stage": name,
        "status": status,
        "exit_code": result.returncode,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "command": list(command),
    }
    with (output / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, sort_keys=True) + "\n")
    print(f"tooling-ci: {name} {status.lower()} ({entry['elapsed_seconds']}s)", flush=True)
    if result.returncode:
        print(result.stdout[-3000:], file=sys.stderr)
        print(result.stderr[-3000:], file=sys.stderr)
        raise RuntimeError(f"{name} failed; inspect {output}")
    return result


def adapted_project_fixture(project: Path, destination: Path) -> Path:
    """Copy a reference into a nested adopter layout without rewriting source.

    Only layout declarations change; native source and expectations stay byte-identical.
    """

    def copy_regular(source: str, target: str) -> str:
        if not stat.S_ISREG(Path(source).lstat().st_mode):
            raise ValueError(f"Cannot copy nonregular fixture input: {source}")
        return shutil.copy2(source, target)

    shutil.copytree(
        project,
        destination,
        symlinks=True,
        copy_function=copy_regular,
        ignore=shutil.ignore_patterns(
            "build", ".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"
        ),
    )

    def fixture_path(value: str) -> Path:
        path = destination
        for component in Path(value).parts:
            path /= component
            if path.is_symlink():
                raise ValueError(f"Cannot relocate or rewrite a linked fixture path: {value}")
        return path

    moves = (
        ("examples/projects", "engineering/reference"),
        ("projects", "designs"),
        ("catalog", "policy"),
    )
    for previous, current in moves:
        source, target = fixture_path(previous), fixture_path(current)
        if source.is_symlink() or (source.exists() and not source.is_dir()):
            raise ValueError(f"Fixture source tree must be an ordinary directory: {previous}")
        if target.exists() or target.is_symlink():
            raise ValueError(f"Fixture relocation target already exists: {current}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            source.rename(target)
        else:
            target.mkdir()

    def relocated(value: str) -> str:
        for previous, current in moves:
            if value == previous or value.startswith(previous + "/"):
                return current + value[len(previous) :]
        return value

    def save(path: Path, document: object) -> None:
        path = fixture_path(path.relative_to(destination).as_posix())
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    discovery_path = fixture_path("policy/projects.json")
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    discovery["catalogs"] = {key: relocated(value) for key, value in discovery["catalogs"].items()}
    discovery["project_roots"] = ["engineering", "designs"]
    discovery["project_depth"] = 2
    save(discovery_path, discovery)
    contract_path = fixture_path("templates/template-contract.json")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["required_paths"] = [relocated(value) for value in contract["required_paths"]]
    save(contract_path, contract)
    for directory in ("engineering/reference", "designs"):
        for path in sorted(fixture_path(directory).glob("*/project.json")):
            if path.is_symlink() or path.parent.is_symlink():
                raise ValueError(f"Fixture manifest cannot be linked: {path}")
            manifest = json.loads(path.read_text(encoding="utf-8"))
            changed = False
            for field in ("shared_source_roots", "shared_inputs"):
                if field in manifest:
                    original = manifest[field]
                    replacement = [relocated(value) for value in original]
                    if replacement != original:
                        manifest[field] = replacement
                        changed = True
            if changed:
                save(path, manifest)
    fixture_path("kicad-tooling.toml").write_text(
        '[layout]\ndiscovery = "policy/projects.json"\n'
        'products = "policy/products.json"\nteam_policy = "policy/team-policy.json"\n'
        'new_project_root = "designs"\n',
        encoding="utf-8",
    )
    return destination


def verify_adapted_project(
    project: Path,
    command: Path,
    output: Path,
    environment: dict[str, str],
) -> None:
    """Exercise the installed wheel against the adapted checkout from an outside cwd."""
    adapted = adapted_project_fixture(project, output / "adapted-project")
    # A separate index makes the portable hygiene gate inspect this fixture's files,
    # rather than accidentally finding the tooling checkout's parent Git repository.
    stage("adapted-git-init", ("git", "init", str(adapted)), output, cwd=output)
    stage("adapted-git-index", ("git", "-C", str(adapted), "add", "--all"), output, cwd=output)
    result = stage(
        "adapted-inventory",
        (str(command), "template", "list", "--root", str(adapted), "--format", "json"),
        output,
        cwd=output,
        environment=environment,
    )
    inventory = json.loads(result.stdout)
    controllers = [item for item in inventory["projects"] if item["id"] == "controller"]
    if (
        inventory["status"] != "PASS"
        or len(controllers) != 1
        or controllers[0]["manifest"] != "engineering/reference/controller/project.json"
    ):
        raise RuntimeError("Adapted inventory did not discover the relocated controller")
    result = stage(
        "adapted-surface",
        (str(command), "surface", "--root", str(adapted), "--format", "json"),
        output,
        cwd=output,
        environment=environment,
    )
    if json.loads(result.stdout)["status"] != "PASS":
        raise RuntimeError("Adapted CLI/MCP declaration parity did not pass")
    result = stage(
        "adapted-verify",
        (
            str(command),
            "verify",
            "--root",
            str(adapted),
            "--project",
            "controller",
            "--format",
            "json",
        ),
        output,
        cwd=output,
        environment=environment,
    )
    report = json.loads(result.stdout)
    if report["status"] != "PASS" or report["depth"] != "portable":
        raise RuntimeError("Adapted project portable verification did not pass")
    if report["build_authorized"] is not False:
        raise RuntimeError("Adapted project verification must not authorize a build")


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
    args = parser.parse_args()
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
                "Install this checkout with python -m pip install -e '.[dev]' "
                "before running its regression suite"
            )
        unit_environment = os.environ.copy()
        unit_environment.pop("KICAD_RUN_NATIVE_SCHEMATIC_GEOMETRY", None)
        unit_environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        unit_command = (sys.executable, "-B", "-I", "-m", "pytest", "-q")
        if args.pytest_markexpr:
            unit_command += ("-m", args.pytest_markexpr)
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
            "pyright",
            (sys.executable, "-m", "pyright", "--pythonpath", sys.executable),
            output,
            cwd=ROOT,
        )
        stage(
            "windows-types",
            (
                sys.executable,
                "-m",
                "pyright",
                "--pythonpath",
                sys.executable,
                "--pythonplatform",
                "Windows",
                "--pythonversion",
                "3.11",
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
        rebuilt_wheel, version = build_distributions(ROOT, output, args.build_python, stage)
        environment_dir = output / "environment"
        venv.EnvBuilder(with_pip=True).create(environment_dir)
        python = environment_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        command = environment_dir / (
            "Scripts/kicad-team.exe" if os.name == "nt" else "bin/kicad-team"
        )
        install = [str(python), "-m", "pip", "install", "--no-cache-dir"]
        stage("install", (*install, f"{rebuilt_wheel}[project,mcp]"), output, cwd=output)
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
                verify_adapted_project(project, command, output, external)
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
