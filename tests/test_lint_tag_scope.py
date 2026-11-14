"""Focused tests for prerelease lint-tag selection metadata and scope."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest

from scripts.lint_gate_scope import (
    LINT_AREAS,
    active_design_lint_rule_ids,
    configured_native_fixtures,
    implementation_paths_by_rule,
    parse_tag_message,
    read_tag_scope,
    required_native_fixtures_by_rule,
    write_github_scope,
)


def test_lint_tag_declares_one_area_and_only_configured_native_fixtures() -> None:
    repository = Path(__file__).resolve().parents[1]
    fixtures = configured_native_fixtures(repository)
    scope = parse_tag_message(
        "CAN peer reference review lint gate\n\n"
        "Lint-Area: interface_lint\n"
        "Native-Fixture: KICAD_RUN_NATIVE_CAN_PEER_REFERENCE_FIXTURES\n",
        fixtures,
    )
    assert scope.pytest_markexpr == "design_lint and interface_lint"
    assert scope.native_fixtures == ("KICAD_RUN_NATIVE_CAN_PEER_REFERENCE_FIXTURES",)


def test_lint_tag_selects_bjt_base_drive_and_its_native_fixture_switch() -> None:
    repository = Path(__file__).resolve().parents[1]
    fixtures = configured_native_fixtures(repository)
    scope = parse_tag_message(
        "BJT base-drive rule gate\n\n"
        "Lint-Rule: component.bjt_base_direct_drive\n"
        "Native-Fixture: KICAD_RUN_NATIVE_COMPONENT_BASE_DRIVE_FIXTURES\n",
        fixtures,
        active_design_lint_rule_ids(),
        required_native_fixtures_by_rule(),
    )

    assert scope.rule_id == "component.bjt_base_direct_drive"
    assert scope.native_fixtures == ("KICAD_RUN_NATIVE_COMPONENT_BASE_DRIVE_FIXTURES",)
    assert scope.pytest_markexpr == (
        'design_lint and (design_lint_rule(rule_id="component.bjt_base_direct_drive") '
        "or rule_gate_integrity)"
    )


def test_lint_tag_areas_are_registered_pytest_markers() -> None:
    repository = Path(__file__).resolve().parents[1]
    configuration = tomllib.loads((repository / "pyproject.toml").read_text(encoding="utf-8"))
    markers = {
        marker.split(":", 1)[0]
        for marker in configuration["tool"]["pytest"]["ini_options"]["markers"]
    }
    assert LINT_AREAS <= markers


@pytest.mark.architecture
def test_architecture_lint_tag_selects_only_architecture_tests() -> None:
    scope = parse_tag_message("Architecture guardrail\n\nLint-Area: architecture\n", frozenset())
    assert scope.pytest_markexpr == "architecture"


def test_design_lint_parent_tag_does_not_repeat_its_marker() -> None:
    scope = parse_tag_message("Complete design-lint slice\n\nLint-Area: design_lint\n", frozenset())
    assert scope.pytest_markexpr == "design_lint"


@pytest.mark.design_lint
@pytest.mark.catalog_lint
def test_catalog_lint_tag_selects_only_catalog_regressions() -> None:
    scope = parse_tag_message("Catalog consistency gate\n\nLint-Area: catalog_lint\n", frozenset())
    assert scope.pytest_markexpr == "design_lint and catalog_lint"


def test_annotated_area_and_rule_tags_resolve_scope_and_write_github_action_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    workflow = repository / ".github/workflows/tooling.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "jobs:\n"
        "  package:\n"
        "    steps:\n"
        "      - name: full acceptance\n"
        "        env:\n"
        "          KICAD_RUN_NATIVE_CAN_PEER_REFERENCE_FIXTURES: '1'\n"
        "          KICAD_RUN_NATIVE_POWER_SEQUENCE_FIXTURES: '1'\n"
        "          KICAD_RUN_NATIVE_SERIAL_PEER_FIXTURES: '1'\n"
        "          KICAD_RUN_NATIVE_DIGITAL_PEER_FIXTURES: '1'\n"
        "  prerelease-lint-gate:\n"
        "    steps: []\n",
        encoding="utf-8",
    )
    (repository / "source.txt").write_text("synthetic\n", encoding="utf-8")
    typecheck_paths = {
        "kicad_tooling/ci_typecheck.py",
        "scripts/ci.py",
        "scripts/lint_gate_scope.py",
        *implementation_paths_by_rule()["power.mapped_sequence_dependency_mismatch"],
        *implementation_paths_by_rule()["bus.serial_peer_reference_review"],
    }
    for relative_path in typecheck_paths:
        target = repository / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# synthetic type-check target\n", encoding="utf-8")
    commands = (
        ("init", "-q"),
        ("config", "user.email", "lint-test@example.invalid"),
        ("config", "user.name", "Lint Test"),
        ("add", "--all"),
        ("commit", "-m", "Synthetic lint gate"),
        (
            "tag",
            "-a",
            "v0.5.0rc1",
            "-m",
            "Synthetic interface lint gate",
            "-m",
            "Lint-Area: interface_lint",
            "-m",
            "Native-Fixture: KICAD_RUN_NATIVE_CAN_PEER_REFERENCE_FIXTURES",
        ),
    )
    for command in commands:
        subprocess.run(("git", *command), cwd=repository, check=True, capture_output=True)

    scope = read_tag_scope("v0.5.0rc1", repository)
    output = tmp_path / "github-output"
    environment = tmp_path / "github-environment"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_ENV", str(environment))
    write_github_scope(scope)

    assert output.read_text(encoding="utf-8") == "markexpr=design_lint and interface_lint\n"
    assert environment.read_text(encoding="utf-8") == (
        "KICAD_RUN_NATIVE_CAN_PEER_REFERENCE_FIXTURES=1\n"
    )

    rule_id = "power.mapped_sequence_dependency_mismatch"
    subprocess.run(
        (
            "git",
            "tag",
            "-a",
            "v0.5.0rc2",
            "-m",
            "Synthetic power lint gate",
            "-m",
            f"Lint-Rule: {rule_id}",
            "-m",
            "Native-Fixture: KICAD_RUN_NATIVE_POWER_SEQUENCE_FIXTURES",
        ),
        cwd=repository,
        check=True,
        capture_output=True,
    )
    rule_scope = read_tag_scope("v0.5.0rc2", repository)
    expected_rule_markexpr = (
        f'design_lint and (design_lint_rule(rule_id="{rule_id}") or rule_gate_integrity)'
    )
    assert rule_scope.pytest_markexpr == expected_rule_markexpr
    assert rule_scope.native_fixtures == ("KICAD_RUN_NATIVE_POWER_SEQUENCE_FIXTURES",)
    expected_typecheck_paths = (
        "kicad_tooling/ci_typecheck.py",
        "kicad_tooling/hwrepo/design_lint_candidate_aggregation.py",
        "kicad_tooling/hwrepo/power_sequences.py",
        "scripts/ci.py",
        "scripts/lint_gate_scope.py",
    )
    assert rule_scope.typecheck_paths == expected_typecheck_paths
    output.write_text("", encoding="utf-8")
    environment.write_text("", encoding="utf-8")
    write_github_scope(rule_scope)
    assert output.read_text(encoding="utf-8") == (
        f"markexpr={expected_rule_markexpr}\ntypecheckpaths={','.join(expected_typecheck_paths)}\n"
    )
    assert environment.read_text(encoding="utf-8") == (
        "KICAD_RUN_NATIVE_POWER_SEQUENCE_FIXTURES=1\n"
    )

    serial_rule_id = "bus.serial_peer_reference_review"
    subprocess.run(
        (
            "git",
            "tag",
            "-a",
            "v0.5.0rc3",
            "-m",
            "Serial reference lint with neighboring native lane",
            "-m",
            f"Lint-Rule: {serial_rule_id}",
            "-m",
            "Native-Fixture: KICAD_RUN_NATIVE_SERIAL_PEER_FIXTURES",
        ),
        cwd=repository,
        check=True,
        capture_output=True,
    )
    with pytest.raises(ValueError, match="requires Native-Fixture declarations"):
        read_tag_scope("v0.5.0rc3", repository)

    subprocess.run(
        (
            "git",
            "tag",
            "-a",
            "v0.5.0rc4",
            "-m",
            "Serial reference lint with required exact native lane",
            "-m",
            f"Lint-Rule: {serial_rule_id}",
            "-m",
            "Native-Fixture: KICAD_RUN_NATIVE_DIGITAL_PEER_FIXTURES",
        ),
        cwd=repository,
        check=True,
        capture_output=True,
    )
    serial_scope = read_tag_scope("v0.5.0rc4", repository)
    assert serial_scope.pytest_markexpr == (
        f'design_lint and (design_lint_rule(rule_id="{serial_rule_id}") or rule_gate_integrity)'
    )
    assert serial_scope.native_fixtures == ("KICAD_RUN_NATIVE_DIGITAL_PEER_FIXTURES",)


@pytest.mark.parametrize(
    ("message", "fixtures", "rule_ids", "error"),
    (
        ("Missing selector", frozenset(), frozenset(), "exactly one Lint-Area or Lint-Rule"),
        (
            "Lint-Area: unknown_theme",
            frozenset(),
            frozenset(),
            "unsupported Lint-Area",
        ),
        (
            "Lint-Rule: power.unknown_rule",
            frozenset(),
            frozenset(),
            "unknown or inactive Lint-Rule",
        ),
        (
            "Lint-Area: power_lint\nLint-Rule: power.mapped_sequence_dependency_mismatch",
            frozenset(),
            frozenset({"power.mapped_sequence_dependency_mismatch"}),
            "exactly one Lint-Area or Lint-Rule",
        ),
        (
            "Lint-Area: interface_lint\nNative-Fixture: KICAD_RUN_NATIVE_NOT_REAL",
            frozenset(),
            frozenset(),
            "absent from full acceptance",
        ),
        (
            (
                "Lint-Area: interface_lint\n"
                "Native-Fixture: KICAD_RUN_NATIVE_CAN_PEER_FIXTURES\n"
                "Native-Fixture: KICAD_RUN_NATIVE_CAN_PEER_FIXTURES"
            ),
            frozenset({"KICAD_RUN_NATIVE_CAN_PEER_FIXTURES"}),
            frozenset(),
            "more than once",
        ),
    ),
)
def test_lint_tag_rejects_ambiguous_or_unconfigured_scope(
    message: str, fixtures: frozenset[str], rule_ids: frozenset[str], error: str
) -> None:
    with pytest.raises(ValueError, match=error):
        parse_tag_message(message, fixtures, rule_ids)
