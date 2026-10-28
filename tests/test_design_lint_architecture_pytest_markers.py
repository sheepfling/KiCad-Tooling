"""Guard lint marker declarations and focused suite boundaries."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from types import MappingProxyType

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.design_lint_pytest_native_marker_registry import PYTEST_NATIVE_LINT_SUITES
from tests.design_lint_return_path_test_markers import RETURN_PATH_LINT_TEST_MODULES
from tests.design_lint_test_markers import (
    design_lint_markers_for_path,
    design_lint_rule_ids_for_test,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]

_RULE_THEME_MARKERS: Mapping[str, str] = MappingProxyType(
    {
        "components": "component_lint",
        "connectors": "connector_lint",
        "interfaces": "interface_lint",
        "pcb": "pcb_lint",
        "power": "power_lint",
        "returns": "return_path_lint",
        "schematic": "schematic_lint",
    }
)


@cache
def _module_pytest_markers(path: str) -> frozenset[str]:
    source_path = Path(__file__).resolve().parents[1] / path
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=path)
    marker_assignments: list[ast.expr] = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            targets = statement.targets
            value = statement.value
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            targets = [statement.target]
            value = statement.value
        else:
            continue
        if any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in targets):
            marker_assignments.append(value)

    return frozenset(
        node.attr
        for expression in marker_assignments
        for node in ast.walk(expression)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
        and node.value.attr == "mark"
    )


def _is_session_scoped_fixture(decorator: ast.expr) -> bool:
    if not isinstance(decorator, ast.Call) or ast.unparse(decorator.func) != "pytest.fixture":
        return False
    for keyword in decorator.keywords:
        value: ast.expr = keyword.value
        if keyword.arg == "scope" and isinstance(value, ast.Constant) and value.value == "session":
            return True
    return False


_DIGITAL_PEER_SUITES: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "test_ci_hosted_digital_peer_spi.py": frozenset({"interface_lint"}),
        "test_ci_hosted_digital_peer_serial.py": frozenset(
            {"connector_lint", "interface_lint", "return_path_lint"}
        ),
        "test_ci_hosted_component_peer_power.py": frozenset(
            {"component_lint", "interface_lint", "power_lint"}
        ),
    }
)

_RETURN_PATH_PEER_REFERENCE_SUITES = frozenset(
    {
        "tests/test_can_peer_reference_review.py",
        "tests/test_connector_split_return_peers.py",
        "tests/test_design_lint_mcp_parity_can_reference.py",
        "tests/test_design_lint_mcp_parity_rs485_reference.py",
        "tests/test_design_lint_mcp_parity_spi_reference.py",
        "tests/test_i2c_peer_reference_native_fixture_lane.py",
        "tests/test_i2c_peer_reference_review.py",
        "tests/test_rs485_peer_reference_native_fixture_lane.py",
        "tests/test_rs485_peer_reference_review.py",
        "tests/test_spi_peer_reference_native_fixture_lane.py",
        "tests/test_spi_peer_reference_review.py",
        "tests/test_usb_data_path_reference_bonds.py",
        "tests/test_usb_inline_bonded_reference_paths.py",
        "tests/test_usb_isolator_peer_reference.py",
        "tests/test_usb_peer_reference_superspeed.py",
        "tests/test_usb_superspeed_peer_reference_native_fixture_lane.py",
        "tests/test_serial_peer_reference_multichannel.py",
        "tests/test_design_lint_serial_parity.py",
        "tests/test_design_lint_mcp_parity_usb_reference.py",
    }
)


@pytest.mark.rule_gate_integrity
def test_active_catalog_fixture_references_receive_their_rule_marker() -> None:
    for rule in rule_catalog().rules:
        if rule.status != "active":
            continue
        references = (
            *rule.fault_fixtures,
            *rule.valid_control_fixtures,
            *rule.metamorphic_fixtures,
        )
        for reference in references:
            parts = reference.split(".")
            assert len(parts) >= 3 and parts[0] == "tests", reference
            module = ".".join(parts[:2])
            test_class = ".".join(parts[2:-1]) or None
            function = parts[-1]
            module_path = f"{module.replace('.', '/')}.py"
            assert rule.rule_id in design_lint_rule_ids_for_test(
                module,
                test_class,
                function,
            ), reference
            area_markers = set(design_lint_markers_for_path(module_path))
            area_markers.update(_module_pytest_markers(module_path))
            assert _RULE_THEME_MARKERS[rule.theme] in area_markers, reference


def test_peer_reference_regressions_are_selectable_in_return_path_scope() -> None:
    assert _RETURN_PATH_PEER_REFERENCE_SUITES <= RETURN_PATH_LINT_TEST_MODULES
    for path in sorted(_RETURN_PATH_PEER_REFERENCE_SUITES):
        markers = design_lint_markers_for_path(path)
        assert "design_lint" in markers
        assert "return_path_lint" in markers


def test_return_path_registry_entries_exist_and_receive_both_lint_markers() -> None:
    tests_root = Path(__file__).parent
    for path in sorted(RETURN_PATH_LINT_TEST_MODULES):
        assert (tests_root.parent / path).is_file(), path
        markers = set(design_lint_markers_for_path(path))
        assert {"design_lint", "return_path_lint"} <= markers


def test_marker_registry_owners_stay_below_review_threshold() -> None:
    for name in (
        "design_lint_return_path_test_markers.py",
        "design_lint_pytest_native_marker_registry.py",
    ):
        owner = Path(__file__).with_name(name)
        assert len(owner.read_text(encoding="utf-8").splitlines()) < 500


def test_cross_theme_architecture_suites_do_not_claim_area_markers() -> None:
    tests_root = Path(__file__).parent
    for filename in (
        "test_design_lint_architecture_pytest_markers.py",
        "test_design_lint_architecture_pytest_collection.py",
        "test_design_lint_architecture_rule_selectors.py",
        "test_design_lint_architecture_theme_suites.py",
    ):
        tree = ast.parse((tests_root / filename).read_text(encoding="utf-8"))
        pytestmark = next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "pytestmark"
                for target in node.targets
            )
        )
        assert isinstance(pytestmark, ast.List)
        marker_names = {ast.unparse(marker) for marker in pytestmark.elts}
        assert marker_names == {"pytest.mark.design_lint", "pytest.mark.architecture"}


def test_external_electrical_template_consumers_are_template_marked() -> None:
    required_support_imports = {
        "tests.electrical_simulation_support": {"install_fixture"},
        "tests.electrical_evidence_support": {
            "create_electrical_evidence_workspace",
            "electrical_evidence_workspace",
        },
        "tests.electrical_parity_support": {"parity_harness"},
    }
    tests_root = Path(__file__).parent
    for source_path in sorted(tests_root.glob("test_*.py")):
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=source_path.name)
        uses_external_electrical_setup = any(
            isinstance(node, ast.ImportFrom)
            and node.module in required_support_imports
            and any(alias.name in required_support_imports[node.module] for alias in node.names)
            for node in ast.walk(tree)
        )
        if uses_external_electrical_setup:
            assert "pytest.mark.template_checkout" in source, source_path.name


def test_tests_using_hosted_reference_checkout_are_template_marked() -> None:
    tests_root = Path(__file__).parent
    for source_path in sorted(tests_root.glob("test_*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=source_path.name)
        uses_hosted_reference_root = any(
            isinstance(node, ast.arg) and node.arg == "hosted_reference_root"
            for node in ast.walk(tree)
        )
        if uses_hosted_reference_root:
            assert "pytest.mark.template_checkout" in source_path.read_text(encoding="utf-8"), (
                source_path.name
            )


def test_native_digital_peer_suites_are_pytest_native_and_theme_scoped() -> None:
    legacy_suite = Path(__file__).with_name("test_ci_hosted_digital_peers.py")
    assert not legacy_suite.exists()

    for filename, area_markers in _DIGITAL_PEER_SUITES.items():
        source_path = Path(__file__).with_name(filename)
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert len(source.splitlines()) < 500
        assert not any(
            isinstance(node, ast.Import)
            and any(alias.name == "unittest" for alias in node.names)
            or isinstance(node, ast.ImportFrom)
            and node.module == "unittest"
            or isinstance(node, ast.ClassDef)
            for node in ast.walk(tree)
        )
        assert any(
            isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
            for node in tree.body
        )
        assert "pytest.mark.design_lint" in source
        assert "pytest.mark.native_kicad" in source
        for marker in area_markers:
            assert f"pytest.mark.{marker}" in source

    serial_path = Path(__file__).with_name("test_ci_hosted_digital_peer_serial.py")
    serial_tree = ast.parse(serial_path.read_text(encoding="utf-8"))
    snapshot_test = next(
        node
        for node in serial_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "test_native_connectivity_snapshot_captures_pin_roles_by_version"
    )
    assert "pytest.mark.evidence_lint" in {
        ast.unparse(decorator) for decorator in snapshot_test.decorator_list
    }

    support_path = Path(__file__).with_name("digital_peer_native_acceptance.py")
    support_tree = ast.parse(support_path.read_text(encoding="utf-8"))
    native_fixture = next(
        node
        for node in support_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "native_digital_peer_results"
    )
    fixture_decorators: list[ast.expr] = native_fixture.decorator_list
    assert any(_is_session_scoped_fixture(decorator) for decorator in fixture_decorators)


def test_focus_lint_suites_are_pytest_native_and_theme_scoped() -> None:
    for filename, area_markers in PYTEST_NATIVE_LINT_SUITES.items():
        source_path = Path(__file__).with_name(filename)
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert len(source.splitlines()) < 500
        assert not any(
            isinstance(node, ast.Import)
            and any(alias.name == "unittest" for alias in node.names)
            or isinstance(node, ast.ImportFrom)
            and node.module == "unittest"
            or isinstance(node, ast.ClassDef)
            for node in ast.walk(tree)
        )
        assert any(
            isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
            for node in tree.body
        )
        assert "pytest.mark.design_lint" in source
        for marker in area_markers:
            assert f"pytest.mark.{marker}" in source
