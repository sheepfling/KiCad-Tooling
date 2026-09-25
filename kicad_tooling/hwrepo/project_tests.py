"""Execute project and dependent-product unittest suites in isolated processes."""
from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from .contracts import read_model, repo_path
from .discovery import load_registry
from .models import CommandEvidence, ProductIndex, ProjectTestsReport


def _run_suite(root: Path, directory: Path) -> CommandEvidence:
    argv = (sys.executable, "-B", "-m", "unittest", "discover", "-s", str(directory), "-v")
    started = datetime.now(UTC).isoformat()
    try:
        result = subprocess.run(argv, cwd=root, text=True, capture_output=True,
                                check=False, timeout=120)
        empty = "Ran 0 tests" in result.stderr
        return CommandEvidence(argv=argv, started_utc=started,
                               returncode=1 if empty else result.returncode,
                               stdout=result.stdout, stderr=result.stderr,
                               error="Test files exist but none were discovered; check package __init__.py files"
                               if empty else None)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandEvidence(argv=argv, started_utc=started, returncode=127, error=str(exc))


def run_tests(root: Path, selected: tuple[str, ...] | None = None,
              max_workers: int = 1) -> ProjectTestsReport:
    if max_workers < 1:
        raise ValueError("Project-test workers must be at least one")
    root = root.resolve()
    registry = load_registry(root)
    directories = {
        f"project-{project.id}": repo_path(root, project.config).parent / "tests"
        for project in registry.projects
        if selected is None or project.id in selected
    }
    index = read_model(repo_path(root, "catalog/products.json"), ProductIndex)
    directories.update({
        f"product-{entry.id}": repo_path(root, entry.path).parent / "tests"
        for entry in index.products
        if selected is None or set(selected).intersection(entry.project_ids)
    })
    suites: list[tuple[str, Path]] = []
    for identifier, directory in sorted(directories.items()):
        if not directory.exists():
            continue
        directory = repo_path(root, directory.relative_to(root).as_posix())
        # A contract-only folder needs no Python process. Nested unittest packages
        # are discovered by the standard runner; each island gets a fresh import scope.
        if not any(directory.rglob("test_*.py")):
            continue
        suites.append((identifier, directory))
    commands: dict[str, CommandEvidence] = {}
    if max_workers == 1:
        commands = {identifier: _run_suite(root, directory) for identifier, directory in suites}
    else:
        # Each island has its own unittest process. Collect futures in sorted order so
        # JSON evidence remains stable regardless of completion order.
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [(identifier, executor.submit(_run_suite, root, directory))
                       for identifier, directory in suites]
            commands = {identifier: future.result() for identifier, future in futures}
    return ProjectTestsReport(status="PASS" if all(command.returncode == 0 for command in
                             commands.values()) else "FAIL", commands=commands)
