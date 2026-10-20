"""Keep catalog types theme-owned and internal imports out of the legacy registry."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import models as shared_models
from kicad_tooling.hwrepo.design_lint_rule_models import (
    DesignLintRuleCatalog,
    DesignLintRuleCatalogDocument,
    DesignLintRuleMetadata,
)
from kicad_tooling.hwrepo.design_lint_rule_types import DesignLintRuleId, DesignLintTheme
from tests.lint_architecture_support import (
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    REPO_ROOT,
    line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]

RULE_MODEL_NAMES = (
    "DesignLintRuleCatalog",
    "DesignLintRuleCatalogDocument",
    "DesignLintRuleMetadata",
)
RULE_TYPE_NAMES = ("DesignLintRuleId", "DesignLintTheme")
LEGACY_MODEL_IMPORTS = {*RULE_MODEL_NAMES, *RULE_TYPE_NAMES}
RULE_OWNER_MODULES = ("design_lint_rule_models.py", "design_lint_rule_types.py")
RULE_FIXTURE_FIELDS = ("fault_fixtures", "valid_control_fixtures", "metamorphic_fixtures")
RULE_THEME_MARKERS = {
    "components": "component_lint",
    "connectors": "connector_lint",
    "interfaces": "interface_lint",
    "power": "power_lint",
    "returns": "return_path_lint",
    "schematic": "schematic_lint",
    "pcb": "pcb_lint",
}


def _fixture_module_path(reference: str) -> Path | None:
    """Find the Python module that owns a catalogued fixture reference."""
    parts = reference.split(".")
    if not parts or parts[0] != "tests":
        return None
    for end in range(len(parts), 1, -1):
        module = REPO_ROOT.joinpath(*parts[:end]).with_suffix(".py")
        if module.is_file():
            return module
        package = REPO_ROOT.joinpath(*parts[:end], "__init__.py")
        if package.is_file():
            return package
    return None


def _module_pytest_markers(path: Path) -> set[str]:
    """Return markers applied through a module-level pytestmark assignment."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assignments = (node for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign)))
    markers: set[str] = set()
    for assignment in assignments:
        targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
        value = assignment.value
        if not value or not any(
            isinstance(target, ast.Name) and target.id == "pytestmark" for target in targets
        ):
            continue
        for node in ast.walk(value):
            if not isinstance(node, ast.Attribute):
                continue
            mark = node.value
            if (
                isinstance(mark, ast.Attribute)
                and mark.attr == "mark"
                and isinstance(mark.value, ast.Name)
                and mark.value.id == "pytest"
            ):
                markers.add(node.attr)
    return markers


def test_catalog_types_have_small_rule_owned_modules() -> None:
    modules = [HWREPO / name for name in RULE_OWNER_MODULES]
    assert all(path.is_file() for path in modules)
    sizes = {path.name: line_count(path) for path in modules}
    oversized = {name: size for name, size in sizes.items() if size >= IMPLEMENTATION_MAX_LINES}
    assert not oversized, f"Keep catalog theme types below 500 lines: {oversized}"


def test_legacy_model_exports_preserve_identity() -> None:
    rule_models = {
        "DesignLintRuleCatalog": DesignLintRuleCatalog,
        "DesignLintRuleCatalogDocument": DesignLintRuleCatalogDocument,
        "DesignLintRuleMetadata": DesignLintRuleMetadata,
    }
    rule_types = {
        "DesignLintRuleId": DesignLintRuleId,
        "DesignLintTheme": DesignLintTheme,
    }
    for name, owner in {**rule_models, **rule_types}.items():
        assert getattr(shared_models, name) is owner
    assert all(
        owner.__module__ == "kicad_tooling.hwrepo.design_lint_rule_models"
        for owner in rule_models.values()
    )


def test_internal_services_import_rule_types_from_their_owner() -> None:
    legacy_imports: list[str] = []
    for path in sorted(HWREPO.glob("*.py")):
        if path.name == "models.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module != "models":
                continue
            if node.level != 1:
                continue
            imported = {alias.name for alias in node.names} & LEGACY_MODEL_IMPORTS
            legacy_imports.extend(f"{path.name}: {name}" for name in sorted(imported))

    assert not legacy_imports, (
        "Internal services must import catalog records and rule IDs from their owners; "
        f"legacy registry imports: {legacy_imports}"
    )


def test_active_rule_fixture_modules_have_design_lint_and_theme_markers() -> None:
    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    modules: dict[Path, set[str]] = {}
    required_theme_markers: dict[Path, set[str]] = {}
    unresolved: list[str] = []
    unmapped_themes: dict[str, str] = {}
    for rule in catalog["rules"]:
        if rule.get("status") != "active":
            continue
        theme = rule.get("theme")
        theme_marker = RULE_THEME_MARKERS.get(theme)
        if theme_marker is None:
            unmapped_themes[rule["rule_id"]] = str(theme)
        for field in RULE_FIXTURE_FIELDS:
            for reference in rule.get(field, []):
                module = _fixture_module_path(reference)
                if module is None:
                    unresolved.append(reference)
                    continue
                modules.setdefault(module, set()).add(reference)
                if theme_marker is not None:
                    required_theme_markers.setdefault(module, set()).add(theme_marker)

    markers_by_module = {path: _module_pytest_markers(path) for path in modules}
    unmarked = {
        path.relative_to(REPO_ROOT).as_posix(): sorted(references_for_module)
        for path, references_for_module in modules.items()
        if "design_lint" not in markers_by_module[path]
    }
    missing_theme_markers = {
        path.relative_to(REPO_ROOT).as_posix(): {
            "missing_markers": sorted(required_theme_markers[path] - markers_by_module[path]),
            "fixtures": sorted(references_for_module),
        }
        for path, references_for_module in modules.items()
        if required_theme_markers[path] - markers_by_module[path]
    }

    assert not unmapped_themes, (
        "Every active design-lint rule theme must map to a focused pytest marker: "
        f"{unmapped_themes}"
    )
    assert not unresolved, f"Active rule fixtures must resolve to Python test modules: {unresolved}"
    assert not unmarked, (
        "Every active rule fault, control, and metamorphic fixture module must carry "
        f"pytest.mark.design_lint so focused runs select it: {unmarked}"
    )
    assert not missing_theme_markers, (
        "Active rule fixture modules need the area marker for each catalogued rule theme; "
        "parity_lint does not replace an area marker: "
        f"{missing_theme_markers}"
    )


@pytest.mark.parametrize(
    ("module_name", "expected_markers"),
    (
        ("test_connector_peer_pin_coverage.py", {"design_lint", "connector_lint"}),
        ("test_connector_footprint_peer_pins.py", {"design_lint", "connector_lint"}),
        ("test_connector_footprint_peer_open.py", {"design_lint", "connector_lint"}),
        (
            "test_connector_footprint_power_input.py",
            {"design_lint", "connector_lint", "power_lint"},
        ),
        (
            "test_connector_footprint_peer_parity.py",
            {"design_lint", "connector_lint", "parity_lint"},
        ),
        (
            "test_connector_footprint_signal_input.py",
            {"design_lint", "connector_lint", "interface_lint"},
        ),
        (
            "test_design_lint_numbered_returns.py",
            {"design_lint", "connector_lint", "return_path_lint"},
        ),
        (
            "test_design_lint_power_pin_patterns.py",
            {"design_lint", "connector_lint", "power_lint"},
        ),
        (
            "test_design_lint_component_power_pins.py",
            {"design_lint", "component_lint", "power_lint"},
        ),
        (
            "test_component_unconnected_power_output.py",
            {"design_lint", "component_lint", "power_lint"},
        ),
        (
            "test_connector_unconnected_power_output.py",
            {"design_lint", "connector_lint", "power_lint"},
        ),
        (
            "test_design_lint_mcp_parity_connector_power_output.py",
            {
                "design_lint",
                "connector_lint",
                "power_lint",
                "parity_lint",
                "slow",
            },
        ),
        (
            "test_design_lint_mcp_parity_unconnected_power_output.py",
            {
                "design_lint",
                "component_lint",
                "power_lint",
                "parity_lint",
                "slow",
            },
        ),
        (
            "test_design_lint_mcp_parity_peer_pins.py",
            {"design_lint", "component_lint", "parity_lint"},
        ),
        (
            "test_design_lint_control_inputs.py",
            {"design_lint", "interface_lint", "power_lint"},
        ),
        (
            "test_design_lint_open_control_inputs.py",
            {"design_lint", "interface_lint", "power_lint"},
        ),
        (
            "test_open_drain_heuristics.py",
            {"design_lint", "interface_lint", "power_lint"},
        ),
        (
            "test_stm32_pin_map.py",
            {"design_lint", "component_lint", "interface_lint"},
        ),
        (
            "test_serial_peer_native_fixture_lane.py",
            {"design_lint", "interface_lint"},
        ),
        (
            "test_serial_reference_bond_native_fixture_lane.py",
            {"design_lint", "interface_lint", "return_path_lint"},
        ),
        (
            "test_design_lint_schematic_readability.py",
            {"design_lint", "schematic_lint"},
        ),
    ),
)
def test_dedicated_lint_suites_have_focused_area_markers(
    module_name: str,
    expected_markers: set[str],
) -> None:
    path = REPO_ROOT / "tests" / module_name
    markers = _module_pytest_markers(path)

    assert expected_markers <= markers
