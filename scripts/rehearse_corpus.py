"""Rehearse a prepared source corpus with installed tooling and disposable projects.

Consumes the disk-kit v0.7 queue as data; never executes downloaded Python.
Run with the Python environment containing the tooling version being evaluated.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import kicad_tooling

NOT_EXERCISED = (
    "transient_and_frequency_simulations", "reviewed_part_selection",
    "cad_download_and_import", "release_revision_package_and_restore",
)


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_report(output: Path, summary: dict[str, Any]) -> None:
    counts = Counter((stage["stage"], stage["status"])
                     for result in summary["results"] for stage in result["stages"])
    lines = ["# Corpus rehearsal", "", f"Run state: **{summary['status']}**.", "",
             f"Recorded {summary['completed']} of {summary['selected']} selected entry points.",
             "RECORDED means the attempts have receipts; it does not mean the designs passed.",
             "This rehearsal does not authorize manufacturing or purchasing.", "",
             "## Stage outcomes", "", "| Stage | Result | Count |",
             "| :--- | :--- | ---: |"]
    for (stage, status), count in sorted(counts.items()):
        lines.append(f"| {stage} | {status} | {count} |")
    lines += ["", "## Coverage still needed", "",
              "These lifecycle stages are NOT_RUN by this corpus driver, including with --native:", ""]
    lines.extend(f"- {name}" for name in NOT_EXERCISED)
    lines += ["", "Grounding and static budgets are checked only when authored requirements exist.",
              "A parts checklist is not a completed purchasing BOM or an approved substitution.",
              "Use the separate quality-gate rehearsal and record engineering review gaps.",
              "", "## Per-project evidence", "",
              "Each linked receipt contains exact commands, JSON stdout, stderr and timings.",
              "Read integrity-before.json and integrity-after.json for source preservation.", "",
              "| Fixture | Repository | Stages |", "| :--- | :--- | :--- |"]
    for result in summary["results"]:
        fixture = result["fixture"]
        states = "; ".join(f"{stage['stage']}: {stage['status']}" for stage in result["stages"])
        repository = fixture["repository"].replace("|", "&#124;")
        lines.append(f"| [{fixture['id']}]({fixture['id']}/result.json) | {repository} | {states} |")
    (output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def signature(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()


def inside(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative)
    if (not relative or parts.is_absolute() or ".." in parts.parts
            or "\\" in relative or ":" in relative):
        raise ValueError(f"Not a portable relative path: {relative}")
    target = root
    for part in parts.parts:
        target /= part
        if target.is_symlink():
            raise ValueError(f"Linked source is not a qualified fixture: {relative}")
    return target


def verify_group(corpus: Path, group: dict[str, Any]) -> list[str]:
    """Check complete inventory before and after runs, without touching the source."""
    inventory = json.loads(inside(corpus, group["inventory_path"]).read_text())
    payload = inventory["files"] if group["source_kind"] == "generated_actions_artifact" else inventory
    if signature(payload) != group["inventory_sha256"]:
        return ["Inventory identity changed; prepare a new queue"]
    if group["source_kind"] == "git_snapshot" and not inventory.get("inventory_complete"):
        return ["Acquisition incomplete"]
    directory = inside(corpus, group["directory"])
    problems: list[str] = []
    expected = {item["path"] for item in inventory["files"]}
    for item in inventory["files"]:
        try:
            if item.get("kind") == "symlink":
                relative = PurePosixPath(item["path"])
                parent = inside(directory, str(relative.parent))
                path = parent / relative.name
                if not path.is_symlink() or os.readlink(path) != item["target"]:
                    problems.append(f"Missing/changed symlink: {item['path']}")
                continue
            path = inside(directory, item["path"])
            if not path.is_file() or digest(path) != item["sha256"]:
                problems.append(f"Missing/changed: {item['path']}")
        except (KeyError, OSError, ValueError) as exc:
            problems.append(str(exc))
    actual: set[str] = set()
    for base, dirs, files in os.walk(directory, followlinks=False):
        links = [name for name in dirs if (Path(base) / name).is_symlink()]
        dirs[:] = [name for name in dirs if name not in links]
        actual.update((Path(base) / name).relative_to(directory).as_posix()
                      for name in [*files, *links])
    problems.extend(f"Uninventoried: {name}" for name in sorted(actual - expected))
    return problems


def environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "PYTHONHOME"} and not key.startswith("GIT_")}


def run(output: Path, name: str, root: Path, *args: str,
        timeout: int = 300) -> dict[str, Any]:
    command = [sys.executable, "-I", "-B", "-m", "kicad_tooling", *args,
               "--root", str(root), "--format", "json"]
    started = time.monotonic()
    try:
        process = subprocess.run(command, cwd=output, env=environment(), text=True,
                                 capture_output=True, timeout=timeout, check=False)
        stdout, stderr, code = process.stdout, process.stderr, process.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or b"").decode(errors="replace")
        stderr = (exc.stderr or b"").decode(errors="replace") + "\nREHEARSAL TIMEOUT"
        code = 124
    (output / f"{name}.stdout.log").write_text(stdout)
    (output / f"{name}.stderr.log").write_text(stderr)
    try:
        report = json.loads(stdout)
        if not isinstance(report, dict):
            raise TypeError("Expected a JSON object")
        if not isinstance(report.get("status"), str):
            raise TypeError("Expected a structured workflow status")
        error = None
    except (ValueError, TypeError) as exc:
        report, error = {}, str(exc)
    result = {"stage": name, "command": command, "returncode": code,
              "status": report.get("status"), "parse_error": error,
              "elapsed_seconds": round(time.monotonic() - started, 3),
              "run_directory": report.get("run_directory"),
              "findings": report.get("findings", [])}
    save(output / f"{name}.json", result)
    return {**result, "report": report}


def copy_template(template: Path, target: Path) -> None:
    shutil.copytree(template, target, symlinks=True, ignore=shutil.ignore_patterns(
        ".git", "build", ".venv", "venv", "__pycache__", "*.pyc", ".DS_Store",
        ".ruff_cache", ".pytest_cache", "*.egg-info"))
    if any((target / "tools").rglob("*.py")) or (target / "kicad_tooling").exists():
        raise ValueError("Use the trimmed template; it must not embed reusable Python tooling")
    for args in (("init", str(target)), ("-C", str(target), "add", "--all")):
        subprocess.run(["git", *args], env=environment(), capture_output=True, check=True)


def file_identity(root: Path) -> dict[str, str]:
    """Bind actual installed code or copied authored data, including uncommitted changes."""
    result: dict[str, str] = {}
    for directory, children, files in os.walk(root, followlinks=False):
        children[:] = sorted(name for name in children if name not in {".git", "__pycache__"})
        for name in sorted(files):
            path = Path(directory) / name
            if not path.is_symlink() and path.is_file() and path.suffix != ".pyc":
                result[path.relative_to(root).as_posix()] = digest(path)
    return result


def execute_one(fixture: dict[str, Any], group: dict[str, Any], corpus: Path,
                baseline: Path, output: Path, toolchain: str,
                native: bool = False) -> dict[str, Any]:
    fixture_id = fixture["id"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", fixture_id):
        raise ValueError(f"Invalid fixture ID: {fixture_id}")
    receipt = output / fixture_id
    receipt.mkdir()
    project = receipt / "project"
    result: dict[str, Any] = {"fixture": fixture, "source_revision": group["revision"],
                              "build_authorized": False, "stages": []}
    try:
        copy_template(baseline, project)
        source = inside(inside(corpus, group["directory"]), fixture["relative_path"])
        args = ("template", "import-project", "--source", str(source),
                "--project-id", fixture_id, "--toolchain", toolchain)
        preview = run(receipt, "preview", project, *args, "--dry-run")
        result["stages"].append(preview)
        if preview["returncode"] == 0:
            imported = run(receipt, "import", project, *args)
            result["stages"].append(imported)
            if imported["returncode"] == 0:
                copied = imported["report"].get("copied_sha256", {})
                folder = project / imported["report"]["directory"] / "kicad"
                result["copied_bytes_match"] = bool(copied) and all(
                    digest(inside(folder, name)) == value for name, value in copied.items())
                for name, arguments in (
                    ("diagnose", ("template", "diagnose", "--project-id", fixture_id)),
                    ("verify", ("verify", "--project", fixture_id)),
                ):
                    result["stages"].append(run(receipt, name, project, *arguments))
                if native:
                    stages = [
                        ("native", ("verify", "--project", fixture_id,
                                    "--depth", "native", "--runner", "container")),
                        ("parts", ("parts", "--project", fixture_id,
                                   "--runner", "container")),
                    ]
                    manifest = json.loads((folder.parent / "project.json").read_text())
                    if manifest.get("kind") in {"pcb", "pcb_only"}:
                        stages.append(("3d", ("visualize", "--project", fixture_id,
                                              "--runner", "container")))
                    for name, arguments in stages:
                        result["stages"].append(run(receipt, name, project, *arguments, timeout=1800))
        result["status"] = "RECORDED"
        if any(row["parse_error"] or row["returncode"] not in (0, 1)
               for row in result["stages"]) or result.get("copied_bytes_match") is False:
            result["status"] = "RUNNER_ERROR"
    except (KeyError, OSError, ValueError, subprocess.SubprocessError) as exc:
        result.update(status="RUNNER_ERROR", error=f"{type(exc).__name__}: {exc}")
    save(receipt / "result.json", result)
    print(f"rehearsal: {fixture_id} {result['status']} "
          + ", ".join(f"{r['stage']}={r['status']}" for r in result["stages"]), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True, help="Prepared queue.json root")
    parser.add_argument("--template-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Fresh run directory")
    parser.add_argument("--toolchain", default="kicad-10.0.5")
    parser.add_argument("--fixture", action="append", default=[], help="Repeat to select IDs")
    parser.add_argument("--limit", type=int, default=10, help="0 selects all ready entry points")
    parser.add_argument("--jobs", type=int, choices=range(1, 9), default=2)
    parser.add_argument("--native", action="store_true",
                        help="Also run exact-container checks/plots, parts and PCB 3D; use a small selection")
    args = parser.parse_args()
    corpus, template = args.corpus.resolve(strict=True), args.template_root.resolve(strict=True)
    output = args.output.resolve()
    if args.limit < 0 or output.is_relative_to(corpus):
        parser.error("Use a nonnegative limit and an output outside source snapshots")
    if args.native and args.jobs != 1:
        parser.error("Native rehearsal requires --jobs 1 to bound KiCad resource use")
    queue = json.loads((corpus / "queue.json").read_text())
    fixtures = [row for row in queue["fixtures"] if row["ready"]
                and (not args.fixture or row["id"] in args.fixture)]
    if set(args.fixture) - {row["id"] for row in fixtures}:
        parser.error("Some requested fixtures are unknown or not ready")
    fixtures = fixtures[:args.limit] if args.limit else fixtures
    if not fixtures:
        parser.error("No ready fixtures selected")
    groups = {row["id"]: row for row in queue["groups"]
              if row["id"] in {fixture["group_id"] for fixture in fixtures}}
    output.mkdir(parents=True, exist_ok=False)
    save(output / "identity.json", {
        "started_utc": datetime.now(UTC).isoformat(), "python": sys.version,
        "tooling_version": importlib.metadata.version("kicad-team-tooling"),
        "template_commit": subprocess.check_output(
            ["git", "-C", str(template), "rev-parse", "HEAD"], text=True).strip(),
        "driver_sha256": digest(Path(__file__)), "queue_sha256": digest(corpus / "queue.json"),
        "installed_package": str(Path(kicad_tooling.__file__).parent),
        "installed_files_sha256": file_identity(Path(kicad_tooling.__file__).parent),
        "scope": "Fresh development rehearsal; no design or release approval",
        "native_requested": args.native,
        "selected": len(fixtures), "catalog_counts": queue.get("counts", {}),
    })
    def integrity() -> dict[str, list[str]]:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            return dict(zip(groups, pool.map(lambda group: verify_group(corpus, group),
                                             groups.values()), strict=True))
    print(f"rehearsal: verifying {len(groups)} input groups", flush=True)
    before = integrity()
    save(output / "integrity-before.json", before)
    baseline = output / "baseline"
    copy_template(template, baseline)
    save(output / "template-files-sha256.json", file_identity(baseline))
    initialized = run(output, "initialize", baseline, "template", "init",
                      "--project-id", "research-rehearsal")
    if initialized["returncode"]:
        return 2
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        pending = [pool.submit(execute_one, row, groups[row["group_id"]], corpus,
                               baseline, output, args.toolchain, args.native)
                   for row in fixtures if not before[row["group_id"]]]
        for future in as_completed(pending):
            results.append(future.result())
            save(output / "progress.json", {"completed": len(results), "selected": len(fixtures)})
    after = integrity()
    save(output / "integrity-after.json", after)
    status = "RECORDED" if (not any(before.values()) and not any(after.values())
                             and all(r["status"] == "RECORDED" for r in results)) else "INCOMPLETE"
    summary = {
        "status": status, "completed": len(results), "selected": len(fixtures),
        "build_authorized": False, "results": sorted(results, key=lambda row: row["fixture"]["id"]),
        "not_exercised": list(NOT_EXERCISED),
    }
    save(output / "summary.json", summary)
    write_report(output, summary)
    print(f"rehearsal: {status}; receipts {output}", flush=True)
    return 0 if status == "RECORDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
