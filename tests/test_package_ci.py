"""Focused tests for package acceptance and prerelease lint selection."""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from kicad_tooling.package_assets import REQUIRED_WHEEL_ASSETS, wheel_contents
from kicad_tooling.package_build import clear_distribution_build_cache
from scripts import ci
from scripts.lint_gate_scope import (
    LINT_AREAS,
    active_design_lint_rule_ids,
    configured_native_fixtures,
    parse_tag_message,
    read_tag_scope,
    write_github_scope,
)


@pytest.mark.parametrize(
    "missing_asset",
    (
        "kicad_tooling/hwrepo/design-lint-rules.json",
        "kicad_tooling/package_build.py",
        "kicad_tooling/hwrepo/component_role_models.py",
        "kicad_tooling/hwrepo/power_path_models.py",
        "kicad_tooling/hwrepo/power_sequence_models.py",
        "kicad_tooling/hwrepo/power_connectivity_models.py",
        "kicad_tooling/hwrepo/analysis_state_models.py",
        "kicad_tooling/hwrepo/crystal_network_models.py",
        "kicad_tooling/hwrepo/pcb_keepout_models.py",
        "kicad_tooling/hwrepo/usb_c_models.py",
    ),
    ids=(
        "rule-catalog",
        "package-build-service",
        "component-role-models",
        "power-path-models",
        "power-sequence-models",
        "power-connectivity-models",
        "analysis-state-models",
        "crystal-network-models",
        "pcb-keepout-models",
        "usb-c-models",
    ),
)
def test_wheel_requires_rule_catalog_and_theme_owned_models(
    tmp_path: Path, missing_asset: str
) -> None:
    wheel = tmp_path / "synthetic.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "synthetic.dist-info/METADATA",
            "Name: kicad-team-tooling\nVersion: 1.0.0\n\n",
        )
        for path in REQUIRED_WHEEL_ASSETS - {missing_asset}:
            archive.writestr(path, "synthetic")
    with pytest.raises(ValueError, match=re.escape(missing_asset)):
        wheel_contents(wheel)


def test_workflow_keeps_full_acceptance_and_scopes_prerelease_tags() -> None:
    repository = Path(__file__).resolve().parents[1]
    workflow = (repository / ".github/workflows/tooling.yml").read_text(encoding="utf-8")
    package_job = workflow.split("  package:\n", 1)[1].split("  prerelease-lint-gate:\n", 1)[0]
    assert "github.event_name != 'push'" in package_job
    assert "github.ref == 'refs/heads/main'" in package_job
    assert "!contains(github.ref_name, 'rc')" in package_job

    lint_job = workflow.split("  prerelease-lint-gate:\n", 1)[1]
    assert "startsWith(github.ref, 'refs/tags/v')" in lint_job
    assert "contains(github.ref_name, 'rc')" in lint_job
    assert 'python scripts/lint_gate_scope.py --tag "$GITHUB_REF_NAME"' in lint_job
    assert '--pytest-markexpr "$PYTEST_MARKEXPR"' in lint_job
    assert "build/acceptance-template" in lint_job
    assert "tooling-lint-gate-${{ github.run_id }}-${{ github.run_attempt }}" in lint_job


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


@pytest.mark.parametrize(
    ("rule_id", "native_fixture"),
    (
        (
            "power.mapped_sequence_dependency_mismatch",
            "KICAD_RUN_NATIVE_POWER_SEQUENCE_FIXTURES",
        ),
        (
            "component.generic_peer_pin_mixed_open",
            "KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES",
        ),
    ),
)
def test_lint_tag_selects_one_active_rule_and_its_configured_native_fixture(
    rule_id: str,
    native_fixture: str,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    fixtures = configured_native_fixtures(repository)
    assert rule_id in active_design_lint_rule_ids()
    assert native_fixture in fixtures

    scope = parse_tag_message(
        "Focused deterministic lint gate\n\n"
        f"Lint-Rule: {rule_id}\n"
        f"Native-Fixture: {native_fixture}\n",
        fixtures,
        active_design_lint_rule_ids(),
    )

    assert scope.area is None
    assert scope.rule_id == rule_id
    assert scope.pytest_markexpr == f'design_lint and design_lint_rule(rule_id="{rule_id}")'
    assert scope.native_fixtures == (native_fixture,)


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
        "          KICAD_RUN_NATIVE_CAN_PEER_REFERENCE_FIXTURES: '1'\n"
        "          KICAD_RUN_NATIVE_POWER_SEQUENCE_FIXTURES: '1'\n"
        "          KICAD_RUN_NATIVE_SERIAL_PEER_FIXTURES: '1'\n"
        "          KICAD_RUN_NATIVE_DIGITAL_PEER_FIXTURES: '1'\n",
        encoding="utf-8",
    )
    (repository / "source.txt").write_text("synthetic\n", encoding="utf-8")
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
    assert rule_scope.pytest_markexpr == f'design_lint and design_lint_rule(rule_id="{rule_id}")'
    assert rule_scope.native_fixtures == ("KICAD_RUN_NATIVE_POWER_SEQUENCE_FIXTURES",)
    output.write_text("", encoding="utf-8")
    environment.write_text("", encoding="utf-8")
    write_github_scope(rule_scope)
    assert output.read_text(encoding="utf-8") == (
        f'markexpr=design_lint and design_lint_rule(rule_id="{rule_id}")\n'
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
        f'design_lint and design_lint_rule(rule_id="{serial_rule_id}")'
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


def test_distribution_build_clears_stale_staging_without_removing_receipts(
    tmp_path: Path,
) -> None:
    stale_module = tmp_path / "build/lib/kicad_tooling/hwrepo/removed_rule.py"
    stale_bdist = tmp_path / "build/bdist.synthetic"
    stale_temp = tmp_path / "build/temp.synthetic"
    receipt = tmp_path / "build/ci/run-1/events.jsonl"
    native_receipt = tmp_path / "build/native/run-1/snapshot.json"
    for path in (
        stale_module,
        stale_bdist / "payload",
        stale_temp / "payload",
        receipt,
        native_receipt,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated", encoding="utf-8")

    clear_distribution_build_cache(tmp_path)

    assert not (tmp_path / "build/lib").exists()
    assert not stale_bdist.exists()
    assert not stale_temp.exists()
    assert receipt.read_text(encoding="utf-8") == "generated"
    assert native_receipt.read_text(encoding="utf-8") == "generated"


@pytest.mark.architecture
def test_ci_driver_applies_only_the_requested_pytest_marker_and_reports_durations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ci, "ROOT", tmp_path)
    monkeypatch.setattr(
        ci.sys,
        "argv",
        ["scripts/ci.py", "--pytest-markexpr", "design_lint and interface_lint"],
    )
    monkeypatch.delenv("KICAD_RUN_NATIVE_SCHEMATIC_GEOMETRY", raising=False)
    stage = Mock()
    stage.return_value.stdout = str(tmp_path / "kicad_tooling/__init__.py")
    monkeypatch.setattr(ci, "stage", stage)
    monkeypatch.setattr(
        ci,
        "build_distributions",
        Mock(side_effect=StopIteration("stop after stage selection")),
    )

    with pytest.raises(StopIteration, match="stop after stage selection"):
        ci.main()

    commands = {call.args[0]: call.args[1] for call in stage.call_args_list}
    assert commands["unit"] == (
        sys.executable,
        "-B",
        "-I",
        "-m",
        "pytest",
        "-q",
        "--durations=10",
        "-m",
        "design_lint and interface_lint",
    )
    assert "design_lint and interface_lint" not in commands["ruff"]


def test_stale_install_is_rejected_before_regressions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ci, "ROOT", tmp_path)
    monkeypatch.setattr(ci.sys, "argv", ["scripts/ci.py"])
    stage = Mock()
    stage.return_value.stdout = str(tmp_path / "other/kicad_tooling/__init__.py")
    monkeypatch.setattr(ci, "stage", stage)

    assert ci.main() == 1
    assert [call.args[0] for call in stage.call_args_list] == ["development-install"]


def test_native_schematic_geometry_gate_remains_opt_in_at_package_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ci, "ROOT", tmp_path)
    monkeypatch.setattr(ci.sys, "argv", ["scripts/ci.py"])
    monkeypatch.setenv("KICAD_RUN_NATIVE_SCHEMATIC_GEOMETRY", "1")
    stage = Mock()
    stage.return_value.stdout = str(tmp_path / "kicad_tooling/__init__.py")
    monkeypatch.setattr(ci, "stage", stage)
    native_geometry = Mock()
    monkeypatch.setattr("kicad_tooling.hwrepo.native_geometry_lane.run", native_geometry)
    monkeypatch.setattr(
        ci,
        "build_distributions",
        Mock(side_effect=StopIteration("stop after checks")),
    )

    with pytest.raises(StopIteration, match="stop after checks"):
        ci.main()

    native_geometry.assert_called_once()
    assert native_geometry.call_args.args[0] == tmp_path
    assert native_geometry.call_args.args[1].parent == tmp_path / "build/ci"
    assert native_geometry.call_args.args[2] is stage
