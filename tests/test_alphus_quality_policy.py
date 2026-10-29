"""Check the repository's advisory Alphus scope and failure semantics."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture
ROOT = Path(__file__).parents[1]


def test_runtime_types_policy_reports_production_and_script_findings(tmp_path: Path) -> None:
    subprocess.run(("git", "init", "--quiet", str(tmp_path)), check=True, timeout=30)
    (tmp_path / "quality-gates.toml").write_bytes((ROOT / "quality-gates.toml").read_bytes())
    for directory in ("kicad_tooling", "scripts", "tests"):
        path = tmp_path / directory / "probe.py"
        path.parent.mkdir()
        path.write_text("def check(value: object) -> bool:\n    return isinstance(value, int)\n")
    args = (sys.executable, "-I", "-m", "alphus", "--root", str(tmp_path))
    report = subprocess.run(
        (*args, "--rule", "runtime-types", "--report", "--json"),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert report.returncode == 0, report.stderr
    findings = json.loads(report.stdout)
    assert len(findings) == 2
    assert any("kicad_tooling/probe.py" in finding for finding in findings)
    assert any("scripts/probe.py" in finding for finding in findings)
    assert all("tests/probe.py" not in finding for finding in findings)

    profile = subprocess.run(
        (*args, "--profile", "runtime-types", "--json"),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert profile.returncode == 1, profile.stderr
    assert json.loads(profile.stdout)["failed"] == 1

    (tmp_path / "quality-gates.toml").write_text("invalid = [")
    invalid = subprocess.run(
        (*args, "--rule", "runtime-types", "--report"),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert invalid.returncode != 0


def test_pydantic_policy_preserves_default_factory_and_reports_positional_default(
    tmp_path: Path,
) -> None:
    subprocess.run(("git", "init", "--quiet", str(tmp_path)), check=True, timeout=30)
    (tmp_path / "quality-gates.toml").write_bytes((ROOT / "quality-gates.toml").read_bytes())
    source = tmp_path / "kicad_tooling" / "probe.py"
    source.parent.mkdir()
    source.write_text(
        "from pydantic import BaseModel, Field\n"
        "class Item(BaseModel):\n"
        "    values: dict[str, int] = Field(default_factory=dict)\n"
        "    count: int = Field(1)\n"
    )
    result = subprocess.run(
        (
            sys.executable,
            "-I",
            "-m",
            "alphus",
            "--root",
            str(tmp_path),
            "--rule",
            "pydantic-practices",
            "--report",
            "--json",
        ),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    findings = json.loads(result.stdout)
    assert [(item["rule_id"], item["line"], item["severity"]) for item in findings] == [
        ("alphus/python/pydantic/style/field-positional-default", 4, "info")
    ]


def test_python_style_policy_exposes_opaque_mapping_category(tmp_path: Path) -> None:
    subprocess.run(("git", "init", "--quiet", str(tmp_path)), check=True, timeout=30)
    (tmp_path / "quality-gates.toml").write_bytes((ROOT / "quality-gates.toml").read_bytes())
    source = tmp_path / "kicad_tooling" / "probe.py"
    source.parent.mkdir()
    source.write_text(
        "from collections.abc import Mapping\n"
        "def opaque(value: Mapping[str, object]) -> None: pass\n"
        "def typed(value: Mapping[str, int]) -> None: pass\n"
    )
    result = subprocess.run(
        (
            sys.executable,
            "-I",
            "-m",
            "alphus",
            "--root",
            str(tmp_path),
            "--rule",
            "python-style",
            "--report",
            "--json",
        ),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["kicad_tooling/probe.py"]["opaque_mappings"] == [2]
    profile = subprocess.run(
        (
            sys.executable,
            "-I",
            "-m",
            "alphus",
            "--root",
            str(tmp_path),
            "--profile",
            "python-style",
            "--json",
        ),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert profile.returncode == 1, profile.stderr
    findings = json.loads(profile.stdout)["steps"][0]["findings"]
    assert any(
        item["rule_id"] == "alphus/python/none/style/opaque-mappings"
        and item["path"] == "kicad_tooling/probe.py"
        and item["line"] == 2
        for item in findings
    )
