"""Tests for annotated lint tags that select explicit pytest modules."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.lint_gate_scope import (
    main,
    parse_tag_message,
    read_message_scope,
    read_tag_scope,
    write_github_scope,
)

pytestmark = pytest.mark.architecture

_PROBE_FIXTURE = "KICAD_RUN_" + "NATIVE_PROBE_FIXTURES"
_OTHER_FIXTURE = "KICAD_RUN_" + "NATIVE_OTHER"
_RS485_FIXTURE = "KICAD_RUN_" + "NATIVE_RS485_DATA_LABEL_MISMATCH_FIXTURES"


def _git(repository: Path, *arguments: str) -> None:
    subprocess.run(("git", *arguments), cwd=repository, check=True, capture_output=True)


def _native_fixture_message(repository: Path) -> str:
    repository.mkdir(parents=True, exist_ok=True)
    (repository / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        'python_classes = ["Test*", "*Tests", "*Test"]\n'
        'python_functions = ["test_*"]\n',
        encoding="utf-8",
    )
    workflow = repository / ".github/workflows/tooling.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(f"{_PROBE_FIXTURE}: '1'\n", encoding="utf-8")
    test_module = repository / "tests/test_native_probe.py"
    test_module.parent.mkdir(parents=True, exist_ok=True)
    return (
        "Lint-Area: architecture\n"
        f"Native-Fixture: {_PROBE_FIXTURE}\n"
        "Test-Path: tests/test_native_probe.py\n"
    )


def test_explicit_test_paths_must_select_a_native_test_guarded_by_each_fixture(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    message = _native_fixture_message(repository)
    (repository / "tests/test_native_probe.py").write_text(
        "import os\n"
        "import pytest\n"
        "@pytest.mark.native_kicad\n"
        "@pytest.mark.skipif(\n"
        f"    os.environ.get('{_PROBE_FIXTURE}') != '1',\n"
        "    reason='requires the declared fixture lane',\n"
        ")\n"
        "def test_native_probe():\n"
        "    pass\n",
        encoding="utf-8",
    )

    scope = read_message_scope(message, repository)

    assert scope.native_fixtures == (_PROBE_FIXTURE,)
    assert scope.test_paths == ("tests/test_native_probe.py",)


@pytest.mark.parametrize(
    "source",
    (
        (
            "import os, pytest\n"
            f"pytestmark = [pytest.mark.native_kicad, pytest.mark.skipif("
            f"os.environ.get('{_PROBE_FIXTURE}') != '1')]\n"
            "def test_native_probe(): pass\n"
        ),
        (
            "import os, pytest\n"
            "@pytest.mark.native_kicad\n"
            f"@pytest.mark.skipif(os.environ.get('{_PROBE_FIXTURE}') != '1')\n"
            "class TestNativeProbe:\n"
            "    def test_export(self): pass\n"
        ),
        (
            "import os, pytest\n"
            "@pytest.mark.native_kicad\n"
            f"@pytest.mark.skipif(os.environ.get('{_PROBE_FIXTURE}') != '1')\n"
            "class NativeProbeTests:\n"
            "    def test_export(self): pass\n"
        ),
        (
            "import os, pytest\n"
            "@pytest.mark.native_kicad\n"
            f"@pytest.mark.skipif(os.environ.get('{_PROBE_FIXTURE}') != '1')\n"
            "class NativeProbeTest:\n"
            "    def test_export(self): pass\n"
        ),
    ),
)
def test_explicit_test_paths_accept_module_and_class_level_native_fixture_markers(
    tmp_path: Path, source: str
) -> None:
    repository = tmp_path / "repository"
    message = _native_fixture_message(repository)
    (repository / "tests/test_native_probe.py").write_text(source, encoding="utf-8")

    scope = read_message_scope(message, repository)

    assert scope.native_fixtures == (_PROBE_FIXTURE,)


@pytest.mark.parametrize(
    "source",
    (
        (
            "import os, pytest\n"
            f"@pytest.mark.skipif(os.environ.get('{_PROBE_FIXTURE}') != '1')\n"
            "def test_native_probe(): pass\n"
        ),
        (
            "import os, pytest\n"
            "@pytest.mark.native_kicad\n"
            f"@pytest.mark.skipif(os.environ.get('{_OTHER_FIXTURE}') != '1')\n"
            "def test_native_probe(): pass\n"
        ),
        (
            "import os, pytest\n"
            "@pytest.mark.native_kicad\n"
            f"@pytest.mark.skipif(os.environ.get('{_PROBE_FIXTURE}') == '1')\n"
            "def test_native_probe(): pass\n"
        ),
        ("import pytest\n@pytest.mark.native_kicad\ndef test_native_probe(): pass\n"),
    ),
)
def test_explicit_test_paths_reject_missing_or_mismatched_native_fixture_guards(
    tmp_path: Path, source: str
) -> None:
    repository = tmp_path / "repository"
    message = _native_fixture_message(repository)
    (repository / "tests/test_native_probe.py").write_text(source, encoding="utf-8")

    with pytest.raises(ValueError, match="no native_kicad test guarded"):
        read_message_scope(message, repository)


def test_annotated_area_tag_resolves_existing_test_paths_and_writes_action_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    workflow = repository / ".github/workflows/tooling.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: synthetic\n", encoding="utf-8")
    paths = ("tests/test_probe.py", "tests/nested/test_peer.py")
    for path in paths:
        target = repository / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# synthetic test module\n", encoding="utf-8")
    _git(repository, "init", "-q")
    _git(repository, "config", "user.email", "lint-test@example.invalid")
    _git(repository, "config", "user.name", "Lint Test")
    _git(repository, "add", "--all")
    _git(repository, "commit", "-m", "Synthetic scoped test modules")
    _git(
        repository,
        "tag",
        "-a",
        "v0.9.0rc1",
        "-m",
        "Synthetic PCB lint gate",
        "-m",
        "Lint-Area: pcb_lint",
        "-m",
        f"Test-Path: {paths[0]}",
        "-m",
        f"Test-Path: {paths[1]}",
    )

    scope = read_tag_scope("v0.9.0rc1", repository)
    assert scope.test_paths == paths
    assert scope.pytest_markexpr == "design_lint and pcb_lint"

    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.delenv("GITHUB_ENV", raising=False)
    write_github_scope(scope)
    assert output.read_text(encoding="utf-8") == (
        "markexpr=design_lint and pcb_lint\n"
        "pytestpaths=tests/test_probe.py,tests/nested/test_peer.py\n"
    )


@pytest.mark.parametrize(
    "path",
    (
        "project/test_probe.py",
        "tests/helper.py",
        "tests/../tests/test_probe.py",
        "/tests/test_probe.py",
        "tests/test_probe.py,tests/test_peer.py",
        "tests/test_bad:name.py",
        "tests/test_bad\\name.py",
    ),
)
def test_lint_tag_rejects_invalid_test_module_paths(path: str) -> None:
    with pytest.raises(ValueError, match="beneath tests/"):
        parse_tag_message(f"Lint-Area: pcb_lint\nTest-Path: {path}\n", frozenset())


def test_lint_rule_tag_cannot_override_catalogued_test_selection() -> None:
    rule_id = "power.mapped_sequence_dependency_mismatch"
    with pytest.raises(ValueError, match="cannot narrow a Lint-Rule selection"):
        parse_tag_message(
            f"Lint-Rule: {rule_id}\nTest-Path: tests/test_probe.py\n",
            frozenset(),
            frozenset({rule_id}),
        )


def test_lint_tag_rejects_duplicate_test_module_paths() -> None:
    with pytest.raises(ValueError, match="paths must be unique"):
        parse_tag_message(
            "Lint-Area: pcb_lint\nTest-Path: tests/test_probe.py\nTest-Path: tests/test_probe.py\n",
            frozenset(),
        )


def test_annotated_area_tag_rejects_a_missing_test_module(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    workflow = repository / ".github/workflows/tooling.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: synthetic\n", encoding="utf-8")
    (repository / "tests").mkdir()
    _git(repository, "init", "-q")
    _git(repository, "config", "user.email", "lint-test@example.invalid")
    _git(repository, "config", "user.name", "Lint Test")
    _git(repository, "add", "--all")
    _git(repository, "commit", "-m", "Synthetic scoped test modules")
    _git(
        repository,
        "tag",
        "-a",
        "v0.9.0rc2",
        "-m",
        "Synthetic PCB lint gate",
        "-m",
        "Lint-Area: pcb_lint",
        "-m",
        "Test-Path: tests/test_missing.py",
    )
    with pytest.raises(ValueError, match="missing or outside tests"):
        read_tag_scope("v0.9.0rc2", repository)


def test_message_file_preflight_validates_rule_scope_without_writing_github_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    message = tmp_path / "lint-tag-message.txt"
    message.write_text(
        f"Lint-Rule: bus.rs485_data_direction_label_mismatch\nNative-Fixture: {_RS485_FIXTURE}\n",
        encoding="utf-8",
    )
    github_output = tmp_path / "github-output"
    github_environment = tmp_path / "github-environment"
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))
    monkeypatch.setenv("GITHUB_ENV", str(github_environment))

    assert main(["--message-file", str(message)]) == 0

    assert capsys.readouterr().out.splitlines() == [
        'markexpr=design_lint and (design_lint_rule(rule_id="bus.rs485_data_direction_label_mismatch") or rule_gate_integrity)',
        f"{_RS485_FIXTURE}=1",
    ]
    assert not github_output.exists()
    assert not github_environment.exists()


def test_message_file_preflight_rejects_missing_required_native_fixture(
    tmp_path: Path,
) -> None:
    message = tmp_path / "lint-tag-message.txt"
    message.write_text(
        "Lint-Rule: bus.rs485_data_direction_label_mismatch\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires Native-Fixture declarations"):
        main(["--message-file", str(message)])
