"""Tests for annotated lint tags that select explicit pytest modules."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from kicad_tooling.lint_gate_typecheck import implementation_paths_by_rule
from scripts.lint_gate_scope import (
    configured_native_fixtures,
    main,
    parse_tag_message,
    read_message_scope,
    read_tag_scope,
    required_native_fixtures_by_rule,
    typecheck_paths_for_area,
    typecheck_paths_for_rule,
    write_github_scope,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.catalog_lint,
    pytest.mark.architecture,
    pytest.mark.rule_gate_integrity,
    pytest.mark.ci_lint,
]

_PROBE_FIXTURE = "KICAD_RUN_" + "NATIVE_PROBE_FIXTURES"
_OTHER_FIXTURE = "KICAD_RUN_" + "NATIVE_OTHER"
_RS485_FIXTURE = "KICAD_RUN_" + "NATIVE_RS485_DATA_LABEL_MISMATCH_FIXTURES"
_EMPTY_PACKAGE_WORKFLOW = (
    "name: synthetic\njobs:\n  package:\n    steps: []\n  prerelease-lint-gate:\n    steps: []\n"
)


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
    workflow.write_text(
        "jobs:\n"
        "  package:\n"
        "    steps:\n"
        "      - name: full acceptance\n"
        "        env:\n"
        f"          {_PROBE_FIXTURE}: '1'\n"
        "  prerelease-lint-gate:\n"
        "    steps:\n"
        "      - name: focused gate\n"
        "        env:\n"
        f"          {_OTHER_FIXTURE}: '1'\n",
        encoding="utf-8",
    )
    test_module = repository / "tests/test_native_probe.py"
    test_module.parent.mkdir(parents=True, exist_ok=True)
    return (
        "Lint-Area: architecture\n"
        f"Native-Fixture: {_PROBE_FIXTURE}\n"
        "Test-Path: tests/test_native_probe.py\n"
    )


def test_configured_native_fixtures_only_uses_full_acceptance_job(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    _native_fixture_message(repository)

    assert configured_native_fixtures(repository) == frozenset({_PROBE_FIXTURE})


@pytest.mark.pcb_lint
def test_fabrication_connectivity_native_fixture_runs_in_full_acceptance() -> None:
    repository = Path(__file__).resolve().parents[1]

    assert "KICAD_RUN_NATIVE_ARTIFACT_CONNECTIVITY" in configured_native_fixtures(repository)


def test_explicit_test_paths_must_select_a_native_test_guarded_by_each_fixture(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    message = _native_fixture_message(repository)
    (repository / "tests/test_native_probe.py").write_text(
        "import pytest\n"
        "pytestmark = pytest.mark.architecture\n"
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
    (repository / "tests/test_native_probe.py").write_text(
        "import pytest\npytestmark = pytest.mark.architecture\n" + source,
        encoding="utf-8",
    )

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
    (repository / "tests/test_native_probe.py").write_text(
        "import pytest\npytestmark = pytest.mark.architecture\n" + source,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no native_kicad test guarded"):
        read_message_scope(message, repository)


def test_annotated_cross_cutting_area_tag_resolves_test_paths_and_action_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    workflow = repository / ".github/workflows/tooling.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(_EMPTY_PACKAGE_WORKFLOW, encoding="utf-8")
    paths = ("tests/test_probe.py", "tests/nested/test_peer.py")
    for path in paths:
        target = repository / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "import pytest\npytestmark = pytest.mark.architecture\n\ndef test_probe():\n    pass\n",
            encoding="utf-8",
        )
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
        "Synthetic architecture gate",
        "-m",
        "Lint-Area: architecture",
        "-m",
        f"Test-Path: {paths[0]}",
        "-m",
        f"Test-Path: {paths[1]}",
    )

    scope = read_tag_scope("v0.9.0rc1", repository)
    assert scope.test_paths == paths
    assert scope.typecheck_paths == ()
    assert scope.pytest_markexpr == "architecture"

    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.delenv("GITHUB_ENV", raising=False)
    write_github_scope(scope)
    assert output.read_text(encoding="utf-8") == (
        "markexpr=architecture\npytestpaths=tests/test_probe.py,tests/nested/test_peer.py\n"
    )


def test_explicit_area_test_path_requires_a_matching_marker(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    workflow = repository / ".github/workflows/tooling.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(_EMPTY_PACKAGE_WORKFLOW, encoding="utf-8")
    probe = repository / "tests/test_probe.py"
    probe.parent.mkdir(parents=True)
    probe.write_text(
        "import pytest\npytestmark = pytest.mark.design_lint\n\ndef test_probe():\n    pass\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no test carrying all Lint-Area"):
        read_message_scope("Lint-Area: interface_lint\nTest-Path: tests/test_probe.py", repository)


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


def test_rule_scope_selects_existing_catalogued_implementation_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = Path(__file__).resolve().parents[1]
    native_fixtures = required_native_fixtures_by_rule()
    rule_id = "connector.mapped_interface_signal_on_named_rail"
    message = "\n".join(
        (
            f"Lint-Rule: {rule_id}",
            *(f"Native-Fixture: {item}" for item in native_fixtures[rule_id]),
        )
    )

    scope = read_message_scope(message, repository)

    assert scope.typecheck_paths == typecheck_paths_for_rule(rule_id)
    assert scope.typecheck_paths == tuple(sorted(set(scope.typecheck_paths)))
    assert all((repository / path).is_file() for path in scope.typecheck_paths)

    output = tmp_path / "github-output"
    environment = tmp_path / "github-environment"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_ENV", str(environment))
    write_github_scope(scope)

    assert output.read_text(encoding="utf-8").splitlines() == [
        f"markexpr={scope.pytest_markexpr}",
        f"typecheckpaths={','.join(scope.typecheck_paths)}",
    ]
    assert environment.read_text(encoding="utf-8").splitlines() == [
        f"{item}=1" for item in scope.native_fixtures
    ]


@pytest.mark.parametrize(
    ("area", "theme"),
    (
        ("component_lint", "components"),
        ("connector_lint", "connectors"),
        ("interface_lint", "interfaces"),
        ("power_lint", "power"),
        ("return_path_lint", "returns"),
        ("schematic_lint", "schematic"),
        ("schematic_text_lint", "schematic"),
        ("schematic_connectivity_lint", "schematic"),
        ("schematic_hierarchy_lint", "schematic"),
        ("pcb_lint", "pcb"),
        ("pcb_reference_lint", "pcb"),
    ),
)
def test_theme_area_typechecks_every_active_catalog_owner_for_that_theme(
    area: str, theme: str
) -> None:
    repository = Path(__file__).resolve().parents[1]
    implementations = implementation_paths_by_rule()
    expected = {
        path
        for rule in rule_catalog(theme=theme, status="active").rules
        for path in typecheck_paths_for_rule(str(rule.rule_id))
    }

    scope = read_message_scope(f"Lint-Area: {area}", repository)

    assert scope.pytest_markexpr == f"design_lint and {area}"
    assert scope.typecheck_paths == tuple(sorted(expected))
    assert all((repository / path).is_file() for path in scope.typecheck_paths)
    assert all(
        set(implementations[str(rule.rule_id)]).issubset(scope.typecheck_paths)
        for rule in rule_catalog(theme=theme, status="active").rules
    )


@pytest.mark.parametrize("area", ("architecture", "evidence_lint", "parity_lint"))
def test_cross_cutting_areas_keep_package_wide_typecheck(area: str) -> None:
    scope = read_message_scope(f"Lint-Area: {area}", Path(__file__).resolve().parents[1])

    assert scope.typecheck_paths == ()


def test_ci_lint_area_selects_gate_modules_and_its_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = Path(__file__).resolve().parents[1]
    message = (
        "Lint-Area: ci_lint\n"
        "Test-Path: tests/test_lint_gate_scope.py\n"
        "Test-Path: tests/test_ci_typecheck.py\n"
        "Test-Path: tests/test_lint_tag_scope.py\n"
        "Test-Path: tests/test_ci_pytest_selection.py"
    )

    scope = read_message_scope(message, repository)

    assert scope.pytest_markexpr == "ci_lint"
    assert scope.test_paths == (
        "tests/test_lint_gate_scope.py",
        "tests/test_ci_typecheck.py",
        "tests/test_lint_tag_scope.py",
        "tests/test_ci_pytest_selection.py",
    )
    assert scope.typecheck_paths == typecheck_paths_for_area("ci_lint")
    assert all((repository / path).is_file() for path in scope.typecheck_paths)

    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.delenv("GITHUB_ENV", raising=False)
    write_github_scope(scope)

    assert output.read_text(encoding="utf-8").splitlines() == [
        "markexpr=ci_lint",
        f"pytestpaths={','.join(scope.test_paths)}",
        f"typecheckpaths={','.join(scope.typecheck_paths)}",
    ]


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
    workflow.write_text(_EMPTY_PACKAGE_WORKFLOW, encoding="utf-8")
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
        "typecheckpaths="
        + ",".join(
            sorted(set(typecheck_paths_for_rule("bus.rs485_data_direction_label_mismatch")))
        ),
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
