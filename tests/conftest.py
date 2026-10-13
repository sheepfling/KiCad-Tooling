"""Apply explicit pytest groups for focused design-lint and cost-aware runs."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.schematic_geometry import (
    SUPPORTED_KICAD_VERSION,
    SUPPORTED_KICAD_VERSIONS,
)
from tests.design_lint_test_markers import (
    design_lint_markers_for_path,
    design_lint_rule_ids_for_test,
)
from tests.execution_test_markers import execution_markers_for_path
from tests.hosted_ci_support import copy_reference_checkout
from tests.support import reference_root

pytest_plugins = (
    "tests.contract_coach_support",
    "tests.digital_peer_voltage_lane_support",
    "tests.digital_peer_native_acceptance",
)

_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def native_schematic_geometry_toolchain() -> tuple[Path, str]:
    """Require the exact native KiCad executable for schematic parity checks."""
    cli_value = os.environ.get("KICAD_GEOMETRY_TEST_CLI")
    if not cli_value:
        pytest.skip("set KICAD_GEOMETRY_TEST_CLI for native KiCad parity tests")
    expected_version = os.environ.get("KICAD_GEOMETRY_TEST_VERSION", SUPPORTED_KICAD_VERSION)
    if expected_version not in SUPPORTED_KICAD_VERSIONS:
        raise ValueError(f"unsupported native geometry test version: {expected_version}")
    cli = Path(cli_value).expanduser()
    if not cli.is_file():
        raise FileNotFoundError("KICAD_GEOMETRY_TEST_CLI does not point to a file")
    version = subprocess.run((str(cli), "version"), capture_output=True, text=True, check=False)
    if version.returncode != 0 or version.stdout.strip() != expected_version:
        pytest.fail(
            f"native geometry test requires KiCad {expected_version}; "
            f"reported {version.stdout.strip()!r}"
        )
    return cli, expected_version


@pytest.fixture
def hosted_reference_root(tmp_path: Path) -> Path:
    """Provide a disposable public-template checkout to focused hosted tests."""
    return copy_reference_checkout(tmp_path / "repository")


@pytest.fixture(scope="module", autouse=True)
def _resolve_legacy_reference_root(request: pytest.FixtureRequest) -> None:
    """Resolve shared template data only if a selected test module needs it."""
    module = request.module
    if getattr(module, "ROOT", None) == Path():
        module.__dict__["ROOT"] = reference_root()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Tag tests by lint scope, catalogued rule, exact toolchain, and cost."""
    for item in items:
        path = item.path.relative_to(_ROOT).as_posix()
        if "architecture" in Path(path).stem:
            item.add_marker(pytest.mark.architecture)
        for marker in design_lint_markers_for_path(path):
            item.add_marker(getattr(pytest.mark, marker))
        module = getattr(item, "module", None)
        module_name = getattr(module, "__name__", "")
        test_class = getattr(item, "cls", None)
        class_name = getattr(test_class, "__qualname__", None)
        function_name = getattr(item, "originalname", item.name.partition("[")[0])
        for rule_id in design_lint_rule_ids_for_test(
            module_name,
            class_name,
            function_name,
        ):
            item.add_marker(pytest.mark.design_lint_rule(rule_id=rule_id))
        for marker in execution_markers_for_path(path):
            item.add_marker(getattr(pytest.mark, marker))
