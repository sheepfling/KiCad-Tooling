"""Synthetic fault/control coverage for the optional Alphus test-quality rule."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architecture, pytest.mark.alphus_experimental]
ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "alphus"

pytest.importorskip("alphus", reason="install the dev-experimental extra to run Alphus checks")


def test_test_quality_reports_brittle_prose_and_respects_test_scope(tmp_path: Path) -> None:
    subprocess.run(("git", "init", "--quiet", str(tmp_path)), check=True, timeout=30)
    (tmp_path / "quality-gates.toml").write_bytes((ROOT / "quality-gates.toml").read_bytes())

    fault = FIXTURES / "test_quality_large_prose.py.fixture"
    control = FIXTURES / "test_quality_structured_control.py.fixture"
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_fault.py").write_bytes(fault.read_bytes())
    (tests / "test_control.py").write_bytes(control.read_bytes())

    excluded = tmp_path / "kicad_tooling" / "test_excluded.py"
    excluded.parent.mkdir()
    excluded.write_bytes(fault.read_bytes())

    command = (
        sys.executable,
        "-I",
        "-m",
        "alphus",
        "--root",
        str(tmp_path),
        "--rule",
        "test-quality",
        "--report",
        "--json",
    )
    first = subprocess.run(command, text=True, capture_output=True, check=False, timeout=30)
    second = subprocess.run(command, text=True, capture_output=True, check=False, timeout=30)
    profile = subprocess.run(
        (
            sys.executable,
            "-I",
            "-m",
            "alphus",
            "--root",
            str(tmp_path),
            "--profile",
            "test-quality",
            "--json",
        ),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert profile.returncode == 0, profile.stderr
    assert first.stdout == second.stdout
    findings = json.loads(first.stdout)
    assert len(findings) == 1
    assert findings[0]["path"] == "tests/test_fault.py"
    assert findings[0]["line"] == 2
    assert findings[0]["severity"] == "warning"
    assert "large exact prose comparison" in findings[0]["message"]

    profile_report = json.loads(profile.stdout)
    assert profile_report["profile"] == "test-quality"
    assert profile_report["severity_counts"] == {"error": 0, "info": 0, "warning": 1}
    profile_findings = profile_report["steps"][0]["findings"]
    assert len(profile_findings) == 1
    assert profile_findings[0]["source"] == "alphus"
    assert {key: value for key, value in profile_findings[0].items() if key != "source"} == (
        findings[0]
    )
