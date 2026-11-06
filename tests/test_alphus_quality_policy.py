"""Check the repository's advisory Alphus scope and failure semantics."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architecture, pytest.mark.alphus_experimental]
ROOT = Path(__file__).parents[1]

pytest.importorskip("alphus", reason="supply the external tool to run these experimental checks")


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
    source_text = (
        "from pydantic import BaseModel, Field\n"
        "class Item(BaseModel):\n"
        "    values: dict[str, int] = Field(default_factory=dict)\n"
        "    count: int = Field(1)\n"
    )
    source.write_text(source_text)
    test_source = tmp_path / "tests" / "probe.py"
    test_source.parent.mkdir()
    test_source.write_text(source_text)
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
    assert len(findings) == 1
    assert findings[0]["path"] == "kicad_tooling/probe.py"
    assert [(item["rule_id"], item["line"], item["severity"]) for item in findings] == [
        ("alphus/python/pydantic/style/field-positional-default", 4, "info")
    ]


def test_python_style_policy_exposes_opaque_mapping_category(tmp_path: Path) -> None:
    subprocess.run(("git", "init", "--quiet", str(tmp_path)), check=True, timeout=30)
    (tmp_path / "quality-gates.toml").write_bytes((ROOT / "quality-gates.toml").read_bytes())
    source = tmp_path / "kicad_tooling" / "probe.py"
    source.parent.mkdir()
    source_text = (
        "from collections.abc import Mapping\n"
        "def opaque(value: Mapping[str, object]) -> None: pass\n"
        "def typed(value: Mapping[str, int]) -> None: pass\n"
    )
    source.write_text(source_text)
    test_source = tmp_path / "tests" / "probe.py"
    test_source.parent.mkdir()
    test_source.write_text(source_text)
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
    findings_by_path = json.loads(result.stdout)
    assert findings_by_path["kicad_tooling/probe.py"]["opaque_mappings"] == [2]
    assert "tests/probe.py" not in findings_by_path
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
    assert profile.returncode == 0, profile.stderr
    profile_report = json.loads(profile.stdout)
    assert profile_report["failure_threshold"] == "error"
    assert profile_report["severity_counts"] == {"error": 0, "info": 0, "warning": 1}
    findings = profile_report["steps"][0]["findings"]
    assert any(
        item["rule_id"] == "alphus/python/none/style/opaque-mappings"
        and item["path"] == "kicad_tooling/probe.py"
        and item["line"] == 2
        and item["severity"] == "warning"
        for item in findings
    )


def test_architecture_candidate_profile_reports_families_as_warnings(
    tmp_path: Path,
) -> None:
    subprocess.run(("git", "init", "--quiet", str(tmp_path)), check=True, timeout=30)
    (tmp_path / "quality-gates.toml").write_bytes((ROOT / "quality-gates.toml").read_bytes())
    family = tmp_path / "kicad_tooling" / "hwrepo"
    family.mkdir(parents=True)
    for name in ("one", "two", "three", "four", "five", "six"):
        (family / f"fixture_family_{name}.py").write_text("VALUE = 1\n")

    result = subprocess.run(
        (
            sys.executable,
            "-I",
            "-m",
            "alphus",
            "--root",
            str(tmp_path),
            "--profile",
            "architecture-candidates",
            "--json",
        ),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["profile"] == "architecture-candidates"
    assert report["failure_threshold"] == "error"
    assert report["severity_counts"] == {"error": 0, "info": 0, "warning": 1}
    findings = report["steps"][0]["findings"]
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "alphus/any/none/maintainability/flat-source-family"
    assert findings[0]["severity"] == "warning"
    assert (
        "Family fixture_family_*: 6 logical units across 6 physical files" in findings[0]["message"]
    )


def test_input_contract_profile_reports_mutation_as_advisory(tmp_path: Path) -> None:
    subprocess.run(("git", "init", "--quiet", str(tmp_path)), check=True, timeout=30)
    (tmp_path / "quality-gates.toml").write_bytes((ROOT / "quality-gates.toml").read_bytes())
    source = tmp_path / "kicad_tooling" / "probe.py"
    source.parent.mkdir()
    source_text = (
        "def normalize(values: dict[str, int]) -> None:\n    values.setdefault('count', 0)\n"
    )
    source.write_text(source_text)
    test_source = tmp_path / "tests" / "probe.py"
    test_source.parent.mkdir()
    test_source.write_text(source_text)

    result = subprocess.run(
        (
            sys.executable,
            "-I",
            "-m",
            "alphus",
            "--root",
            str(tmp_path),
            "--profile",
            "input-contracts",
            "--json",
        ),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["profile"] == "input-contracts"
    assert report["failure_threshold"] == "error"
    assert report["severity_counts"] == {"error": 0, "info": 0, "warning": 1}
    findings = report["steps"][0]["findings"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding["rule_id"] == "alphus/python/none/correctness/argument-mutation"
    assert finding["path"] == "kicad_tooling/probe.py"
    assert finding["severity"] == "warning"


def test_complexity_candidate_profile_is_provisional_and_scoped() -> None:
    policy = tomllib.loads((ROOT / "quality-gates.toml").read_text())
    rule = policy["checks"]["cyclomatic_complexity"]
    assert rule["maximum"] == 30
    assert rule["severity"] == "warning"
    assert rule["backends"] == [{"language": "python", "backend": "ruff", "version": "0.16.1"}]
    assert rule["files"]["include"] == ["kicad_tooling/hwrepo/**/*.py"]
    step = next(
        row
        for row in policy["orchestration"]["steps"]
        if row.get("rule") == "cyclomatic-complexity"
    )
    assert step["rollout"] == "provisional"


def test_module_role_boundary_profile_blocks_reintroduced_implementations(
    tmp_path: Path,
) -> None:
    policy = tomllib.loads((ROOT / "quality-gates.toml").read_text())
    module_rules = policy["checks"]["module_roles"]["modules"]
    guarded_paths = {item["path"] for item in module_rules}
    assert {
        "kicad_tooling/hwrepo/cross_probe.py",
        "kicad_tooling/hwrepo/design_lint_candidate_aggregation.py",
        "kicad_tooling/hwrepo/governance_lint.py",
    } <= guarded_paths
    step = next(
        row for row in policy["orchestration"]["steps"] if row.get("rule") == "module-roles"
    )
    assert step["rollout"] == "mainline"

    subprocess.run(("git", "init", "--quiet", str(tmp_path)), check=True, timeout=30)
    config = tmp_path / "quality-gates.toml"
    config.write_bytes((ROOT / "quality-gates.toml").read_bytes())
    for rule in module_rules:
        path = tmp_path / rule["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("VALUE = True\n")

    command = (
        sys.executable,
        "-I",
        "-m",
        "alphus",
        "--root",
        str(tmp_path),
        "--config",
        "quality-gates.toml",
        "--profile",
        "module-role-boundaries",
        "--json",
    )
    valid = subprocess.run(command, text=True, capture_output=True, check=False, timeout=30)
    assert valid.returncode == 0, valid.stderr
    assert json.loads(valid.stdout)["severity_counts"] == {
        "error": 0,
        "info": 0,
        "warning": 0,
    }

    coordinator = tmp_path / "kicad_tooling/hwrepo/design_lint_candidate_aggregation.py"
    coordinator.write_text("def scan_connector_candidates(*args, **kwargs):\n    return ()\n")
    invalid = subprocess.run(command, text=True, capture_output=True, check=False, timeout=30)
    assert invalid.returncode == 1, invalid.stderr
    report = json.loads(invalid.stdout)
    assert report["failed"] == 1
    findings = report["steps"][0]["findings"]
    assert len(findings) == 1
    assert findings[0]["path"] == "kicad_tooling/hwrepo/design_lint_candidate_aggregation.py"
    assert findings[0]["rule_id"].endswith("/architecture/forbidden-module-definition")


def test_mainline_module_role_profile_runs_in_package_ci() -> None:
    tree = ast.parse((ROOT / "scripts/ci.py").read_text())
    stages = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "stage"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "alphus-module-role-boundaries"
    ]
    (stage,) = stages
    command = stage.args[1]
    assert isinstance(command, ast.Tuple)
    assert [
        element.value
        for element in command.elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    ] == [
        "-I",
        "-m",
        "alphus",
        "--root",
        "--config",
        "quality-gates.toml",
        "--profile",
        "module-role-boundaries",
        "--json",
    ]


def test_shared_utility_duplication_profile_is_a_mainline_ci_gate(
    tmp_path: Path,
) -> None:
    policy = tomllib.loads((ROOT / "quality-gates.toml").read_text())
    shared_utilities = policy["checks"]["shared_utilities"]
    assert shared_utilities["extensions"] == [".py"]
    assert shared_utilities["exclude"] == ["scripts/**/*.py", "tests/**/*.py"]
    assert shared_utilities["canonical_file_hash_path"] == "kicad_tooling/hwrepo/evidence.py"
    assert shared_utilities["canonical_file_hash_function"] == "digest"
    step = next(
        row for row in policy["orchestration"]["steps"] if row.get("rule") == "shared-utilities"
    )
    assert step["rollout"] == "mainline"
    assert (
        next(
            row["name"]
            for row in policy["orchestration"]["profiles"]
            if row["steps"] == [step["name"]]
        )
        == "shared-utility-duplication"
    )

    tree = ast.parse((ROOT / "scripts/ci.py").read_text())
    stages = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "stage"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "alphus-shared-utility-duplication"
    ]
    (stage,) = stages
    command = stage.args[1]
    assert isinstance(command, ast.Tuple)
    assert [
        element.value
        for element in command.elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    ] == [
        "-I",
        "-m",
        "alphus",
        "--root",
        "--config",
        "quality-gates.toml",
        "--profile",
        "shared-utility-duplication",
        "--json",
    ]

    subprocess.run(("git", "init", "--quiet", str(tmp_path)), check=True, timeout=30)
    config = tmp_path / "quality-gates.toml"
    config.write_bytes((ROOT / "quality-gates.toml").read_bytes())
    command = (
        sys.executable,
        "-I",
        "-m",
        "alphus",
        "--root",
        str(tmp_path),
        "--config",
        "quality-gates.toml",
        "--profile",
        "shared-utility-duplication",
        "--json",
    )
    clean = subprocess.run(command, text=True, capture_output=True, check=False, timeout=30)
    assert clean.returncode == 0, clean.stderr
    assert json.loads(clean.stdout)["severity_counts"] == {
        "error": 0,
        "info": 0,
        "warning": 0,
    }

    duplicate_helper = (
        "def normalize(value):\n"
        "    stripped = value.strip()\n"
        "    normalized = stripped.lower()\n"
        "    return normalized\n"
    )
    for name in ("first.py", "second.py"):
        path = tmp_path / "kicad_tooling/hwrepo" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(duplicate_helper)
    duplicate = subprocess.run(command, text=True, capture_output=True, check=False, timeout=30)
    assert duplicate.returncode == 1, duplicate.stderr
    report = json.loads(duplicate.stdout)
    assert report["failed"] == 1
    findings = report["steps"][0]["findings"]
    assert len(findings) == 1
    assert findings[0]["rule_id"].endswith("/maintainability/duplicate-helper")
    assert "first.py" in findings[0]["message"]
    assert "second.py" in findings[0]["message"]
