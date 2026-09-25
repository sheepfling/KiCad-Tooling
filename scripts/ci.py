"""Run package checks and an installed-wheel rehearsal with retained logs."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import venv
import zipfile
from datetime import UTC, datetime
from email.parser import Parser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def wheel_contents(wheel: Path) -> tuple[str, dict[str, bytes]]:
    """Read authoritative metadata and package payload for distribution comparison."""
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [name for name in archive.namelist()
                          if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError(f"Expected one distribution metadata file in {wheel}")
        metadata = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))
        version = metadata["Version"]
        if metadata["Name"] != "kicad-team-tooling" or not version:
            raise ValueError(f"Unexpected distribution metadata in {wheel}")
        payload = {name: archive.read(name) for name in archive.namelist()
                   if name.startswith("kicad_tooling/") or name == metadata_names[0]}
        required = {"kicad_tooling/tool-surfaces.json", "kicad_tooling/py.typed",
                    "kicad_tooling/hwrepo/kicad_library_license.txt"}
        if not required <= payload.keys():
            raise ValueError(f"Missing package assets in {wheel}: {required - payload.keys()}")
        return version, payload


def only_artifact(directory: Path, pattern: str) -> Path:
    matches = tuple(directory.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {pattern} in {directory}")
    return matches[0]


def stage(name: str, command: tuple[str, ...], output: Path, *, cwd: Path,
          environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    started = time.monotonic()
    print(f"tooling-ci: {name} started", flush=True)
    result = subprocess.run(command, cwd=cwd, env=environment,
                            capture_output=True, text=True, check=False)
    (output / f"{name}.stdout.log").write_text(result.stdout, encoding="utf-8")
    (output / f"{name}.stderr.log").write_text(result.stderr, encoding="utf-8")
    status = "PASS" if result.returncode == 0 else "FAIL"
    entry = {
        "time_utc": datetime.now(UTC).isoformat(), "stage": name,
        "status": status,
        "exit_code": result.returncode,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "command": list(command),
    }
    with (output / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, sort_keys=True) + "\n")
    print(f"tooling-ci: {name} {status.lower()} ({entry['elapsed_seconds']}s)",
          flush=True)
    if result.returncode:
        print(result.stdout[-3000:], file=sys.stderr)
        print(result.stderr[-3000:], file=sys.stderr)
        raise RuntimeError(f"{name} failed; inspect {output}")
    return result


def build_distributions(output: Path, build_python: str) -> tuple[Path, str]:
    """Prove a source archive reproduces its wheel without access to Git metadata."""
    wheels = output / "wheels"
    wheels.mkdir()
    stage("wheel", (build_python, "-m", "build", "--wheel", "--no-isolation",
                    "--outdir", str(wheels), "."),
          output, cwd=ROOT)
    checkout_wheel = only_artifact(wheels, "kicad_team_tooling-*.whl")
    version, payload = wheel_contents(checkout_wheel)
    sdists = output / "sdists"
    sdists.mkdir()
    stage("sdist", (build_python, "-m", "build", "--sdist", "--no-isolation",
                    "--outdir", str(sdists), "."), output, cwd=ROOT)
    sdist = only_artifact(sdists, "kicad_team_tooling-*.tar.gz")
    rebuilt_dir = output / "rebuilt-wheels"
    rebuilt_dir.mkdir()
    with tempfile.TemporaryDirectory(prefix="kicad-tooling-sdist-") as temporary:
        extracted = Path(temporary)
        with tarfile.open(sdist) as archive:
            archive.extractall(extracted, filter="data")
        source = only_artifact(extracted, "kicad_team_tooling-*")
        if any(source.rglob(".git")) or any((parent / ".git").exists()
                                           for parent in source.parents):
            raise RuntimeError("Source rebuild must have no Git metadata or parent checkout")
        stage("sdist-wheel", (build_python, "-m", "build", "--wheel", "--no-isolation",
                              "--outdir", str(rebuilt_dir), "."), output, cwd=source)
    rebuilt_wheel = only_artifact(rebuilt_dir, "kicad_team_tooling-*.whl")
    rebuilt_version, rebuilt_payload = wheel_contents(rebuilt_wheel)
    if (version, payload) != (rebuilt_version, rebuilt_payload):
        raise RuntimeError("Source distribution rebuild changed package metadata or payload")
    (output / "packaging.json").write_text(json.dumps({
        "version": version, "source_distribution_version": rebuilt_version,
        "package_files": len(payload), "source_distribution_contains_git": False,
        "status": "PASS",
    }, indent=2) + "\n", encoding="utf-8")
    return rebuilt_wheel, version



def adapted_project_fixture(project: Path, destination: Path) -> Path:
    """Copy the known reference into a nested adopter layout without rewriting CAD.

    Keep products, libraries, templates and documentation in place. Only discovery,
    template presence expectations and project shared-path declarations describe the
    moved trees; their native source and engineering expectations remain byte-identical.
    """
    def copy_regular(source: str, target: str) -> str:
        if not stat.S_ISREG(Path(source).lstat().st_mode):
            raise ValueError(f"Cannot copy nonregular fixture input: {source}")
        return shutil.copy2(source, target)

    shutil.copytree(
        project, destination, symlinks=True, copy_function=copy_regular,
        ignore=shutil.ignore_patterns("build", ".git", ".venv", "__pycache__",
                                      ".pytest_cache", ".ruff_cache"),
    )
    def fixture_path(value: str) -> Path:
        path = destination
        for component in Path(value).parts:
            path /= component
            if path.is_symlink():
                raise ValueError(f"Cannot relocate or rewrite a linked fixture path: {value}")
        return path

    moves = (("examples/projects", "engineering/reference"),
             ("projects", "designs"), ("catalog", "policy"))
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
                return current + value[len(previous):]
        return value

    def save(path: Path, document: object) -> None:
        path = fixture_path(path.relative_to(destination).as_posix())
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    discovery_path = fixture_path("policy/projects.json")
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    discovery["catalogs"] = {key: relocated(value)
                             for key, value in discovery["catalogs"].items()}
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
        'new_project_root = "designs"\n', encoding="utf-8",
    )
    return destination


def verify_adapted_project(
    project: Path, command: Path, output: Path, environment: dict[str, str],
) -> None:
    """Exercise the installed wheel against the adapted checkout from an outside cwd."""
    adapted = adapted_project_fixture(project, output / "adapted-project")
    # A separate index makes the portable hygiene gate inspect this fixture's files,
    # rather than accidentally finding the tooling checkout's parent Git repository.
    stage("adapted-git-init", ("git", "init", str(adapted)), output, cwd=output)
    stage("adapted-git-index", ("git", "-C", str(adapted), "add", "--all"),
          output, cwd=output)
    result = stage("adapted-inventory", (str(command), "template", "list", "--root",
                   str(adapted), "--format", "json"), output, cwd=output,
                   environment=environment)
    inventory = json.loads(result.stdout)
    controllers = [item for item in inventory["projects"] if item["id"] == "controller"]
    if (inventory["status"] != "PASS" or len(controllers) != 1
            or controllers[0]["manifest"] != "engineering/reference/controller/project.json"):
        raise RuntimeError("Adapted inventory did not discover the relocated controller")
    result = stage("adapted-surface", (str(command), "surface", "--root", str(adapted),
                   "--format", "json"), output, cwd=output, environment=environment)
    if json.loads(result.stdout)["status"] != "PASS":
        raise RuntimeError("Adapted CLI/MCP declaration parity did not pass")
    result = stage("adapted-verify", (str(command), "verify", "--root", str(adapted),
                   "--project", "controller", "--format", "json"), output, cwd=output,
                   environment=environment)
    report = json.loads(result.stdout)
    if report["status"] != "PASS" or report["depth"] != "portable":
        raise RuntimeError("Adapted project portable verification did not pass")
    if report["build_authorized"] is not False:
        raise RuntimeError("Adapted project verification must not authorize a build")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path,
                        help="Optional separate populated template checkout for integration")
    parser.add_argument("--build-python", default=sys.executable,
                        help="Python with build, setuptools and setuptools-scm for packaging")
    parser.add_argument("--offline-dependency-path", type=Path,
                        help="Local site-packages for an offline installed-wheel rehearsal")
    parser.add_argument("--skip-mdrepo", action="store_true",
                        help="Offline local rehearsal only; hosted CI must run mdrepo")
    parser.add_argument("--rumdl-path", type=Path,
                        default=Path(sys.executable).with_name("rumdl"))
    args = parser.parse_args()
    logs = ROOT / "build/ci"
    logs.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="run-", dir=logs))
    try:
        stage("unit", (sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"),
              output, cwd=ROOT)
        stage("ruff", (sys.executable, "-m", "ruff", "check", "--no-cache",
                       "kicad_tooling", "tests", "scripts"), output, cwd=ROOT)
        stage("pyright", (sys.executable, "-m", "pyright", "--pythonpath", sys.executable),
              output, cwd=ROOT)
        stage("rumdl", (str(args.rumdl_path), "check", ".",
                        "--no-cache"), output, cwd=ROOT)
        if not args.skip_mdrepo:
            stage("mdrepo", (sys.executable, "-m", "mdrepo", "check", "."),
                  output, cwd=ROOT)
        rebuilt_wheel, version = build_distributions(output, args.build_python)
        environment_dir = output / "environment"
        venv.EnvBuilder(with_pip=True).create(environment_dir)
        python = environment_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        command = environment_dir / ("Scripts/kicad-team.exe" if os.name == "nt"
                                     else "bin/kicad-team")
        install = [str(python), "-m", "pip", "install", "--no-cache-dir"]
        if args.offline_dependency_path is not None:
            install.append("--no-deps")
        stage("install", (*install, f"{rebuilt_wheel}[mcp]"), output, cwd=output)
        external = os.environ.copy()
        external.pop("PYTHONPATH", None)
        if args.offline_dependency_path is not None:
            dependencies = args.offline_dependency_path.resolve()
            if not dependencies.is_dir() or any(char in str(dependencies) for char in "\r\n"):
                raise ValueError("Offline dependencies must be an ordinary directory path")
            located = stage("installed-site-packages", (str(python), "-I", "-c",
                            "import sysconfig; print(sysconfig.get_path('purelib'))"),
                            output, cwd=output, environment=external)
            site_packages = Path(located.stdout.strip()).resolve()
            if not site_packages.is_relative_to(environment_dir.resolve()):
                raise RuntimeError("Installed interpreter resolved site-packages outside its environment")
            # Append dependency lookup after this wheel's site-packages. PYTHONPATH
            # would let an older tooling package in the dependency cache shadow it.
            (site_packages / "offline_dependencies.pth").write_text(
                str(dependencies) + "\n", encoding="utf-8",
            )
        origin = stage("installed-origin", (str(python), "-I", "-c",
                       "import kicad_tooling; print(kicad_tooling.__file__)"),
                       output, cwd=output, environment=external)
        if not Path(origin.stdout.strip()).resolve().is_relative_to(environment_dir.resolve()):
            raise RuntimeError("Rehearsal imported tooling outside the installed wheel environment")
        installed_version = stage("installed-version", (str(command), "--version"),
                                  output, cwd=output, environment=external)
        if installed_version.stdout.strip() != f"kicad-team-tooling {version}":
            raise RuntimeError("Installed command reported an unexpected package version")
        project = args.project_root.resolve() if args.project_root else None
        if project is not None:
            inventory = stage("external-inventory", (str(command), "template", "list",
                        "--root", str(project), "--format", "json"), output, cwd=output,
                        environment=external)
            if json.loads(inventory.stdout)["status"] != "PASS":
                raise RuntimeError("External inventory did not pass")
            surface = stage("external-surface", (str(command), "surface", "--root",
                        str(project), "--format", "json"), output, cwd=output,
                        environment=external)
            if json.loads(surface.stdout)["status"] != "PASS":
                raise RuntimeError("External CLI/MCP declaration parity did not pass")
            if (project / "examples/projects/controller/project.json").is_file():
                stage("external-verify", (str(command), "verify", "--root", str(project),
                      "--project", "controller", "--format", "json"), output, cwd=output,
                      environment=external)
                verify_adapted_project(project, command, output, external)
        print(f"tooling-ci: logs {output}")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"tooling-ci: {exc}; logs {output}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
