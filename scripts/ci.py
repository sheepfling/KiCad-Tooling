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
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def stage(name: str, command: tuple[str, ...], output: Path, *, cwd: Path,
          environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    started = time.monotonic()
    print(f"tooling-ci: {name} started", flush=True)
    result = subprocess.run(command, cwd=cwd, env=environment,
                            capture_output=True, text=True, check=False)
    (output / f"{name}.stdout.log").write_text(result.stdout, encoding="utf-8")
    (output / f"{name}.stderr.log").write_text(result.stderr, encoding="utf-8")
    entry = {
        "time_utc": datetime.now(UTC).isoformat(), "stage": name,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "exit_code": result.returncode,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "command": list(command),
    }
    with (output / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, sort_keys=True) + "\n")
    print(f"tooling-ci: {name} {entry['status'].lower()} ({entry['elapsed_seconds']}s)",
          flush=True)
    if result.returncode:
        print(result.stdout[-3000:], file=sys.stderr)
        print(result.stderr[-3000:], file=sys.stderr)
        raise RuntimeError(f"{name} failed; inspect {output}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path,
                        help="Optional separate populated template checkout for integration")
    parser.add_argument("--build-python", default=sys.executable,
                        help="Python with setuptools for wheel building")
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
        stage("rumdl", (str(args.rumdl_path), "check", ".",
                        "--no-cache"), output, cwd=ROOT)
        if not args.skip_mdrepo:
            stage("mdrepo", (sys.executable, "-m", "mdrepo", "check", "."),
                  output, cwd=ROOT)
        wheels = output / "wheels"
        wheels.mkdir()
        stage("wheel", (args.build_python, "-m", "pip", "wheel", "--no-deps",
                        "--no-build-isolation", "--no-cache-dir", "--wheel-dir", str(wheels), "."),
              output, cwd=ROOT)
        built = tuple(wheels.glob("kicad_team_tooling-*.whl"))
        if len(built) != 1:
            raise RuntimeError(f"Expected exactly one tooling wheel in {wheels}")
        environment_dir = output / "environment"
        venv.EnvBuilder(with_pip=True).create(environment_dir)
        python = environment_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        command = environment_dir / ("Scripts/kicad-team.exe" if os.name == "nt"
                                     else "bin/kicad-team")
        install = [str(python), "-m", "pip", "install", "--no-cache-dir"]
        if args.offline_dependency_path is not None:
            install.append("--no-deps")
        stage("install", (*install, str(built[0])), output, cwd=output)
        project = args.project_root.resolve() if args.project_root else None
        if project is not None:
            if not (project / "catalog/projects.json").is_file():
                raise ValueError(f"Not a KiCad project checkout: {project}")
            external = os.environ.copy()
            external.pop("PYTHONPATH", None)
            if args.offline_dependency_path is not None:
                external["PYTHONPATH"] = str(args.offline_dependency_path.resolve())
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
        print(f"tooling-ci: logs {output}")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"tooling-ci: {exc}; logs {output}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
