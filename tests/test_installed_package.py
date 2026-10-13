"""Package boundary checks using a disposable project checkout."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.surface import inspect_tool_surfaces

SOURCE_ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.slow


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "catalog").mkdir()
    (tmp_path / "projects").mkdir()
    (tmp_path / "catalog/projects.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "catalogs": {
                    "parts": "catalog/parts.json",
                    "interfaces": "catalog/interfaces.json",
                    "libraries": "catalog/libraries.json",
                    "toolchains": "catalog/toolchains.json",
                    "release_policies": "catalog/release-policies.json",
                },
                "project_roots": ["projects"],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "catalog/toolchains.json").write_text(
        '{"schema_version":"0.1","toolchains":[]}\n', encoding="utf-8"
    )
    (tmp_path / "catalog/products.json").write_text(
        '{"schema_version":"1","products":[]}\n', encoding="utf-8"
    )
    return tmp_path


def run_cli(project: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    return subprocess.run(
        (sys.executable, "-I", "-B", "-m", "kicad_tooling", *args),
        cwd=cwd or project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_inventory_uses_project_checkout_not_package_source(project: Path) -> None:
    result = run_cli(project, "template", "list", "--format", "json")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "PASS"
    assert report["projects"] == []


def test_explicit_root_works_from_another_directory(project: Path) -> None:
    result = run_cli(
        project,
        "template",
        "list",
        "--root",
        str(project),
        "--format",
        "json",
        cwd=SOURCE_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "PASS"


def test_surface_catalog_belongs_to_tooling_package(project: Path) -> None:
    report = inspect_tool_surfaces(project)
    assert report.coverage_status == "PASS", report.issues
    assert report.parity_status == "PASS", report.issues
