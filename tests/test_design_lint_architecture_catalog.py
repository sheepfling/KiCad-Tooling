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

pytestmark = pytest.mark.design_lint

RULE_MODEL_NAMES = (
    "DesignLintRuleCatalog",
    "DesignLintRuleCatalogDocument",
    "DesignLintRuleMetadata",
)
RULE_TYPE_NAMES = ("DesignLintRuleId", "DesignLintTheme")
LEGACY_MODEL_IMPORTS = {*RULE_MODEL_NAMES, *RULE_TYPE_NAMES}
RULE_OWNER_MODULES = ("design_lint_rule_models.py", "design_lint_rule_types.py")
RULE_FIXTURE_FIELDS = ("fault_fixtures", "valid_control_fixtures", "metamorphic_fixtures")


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


def _has_module_design_lint_marker(path: Path) -> bool:
    """Return whether a test module applies pytest's design_lint marker."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assignments = (node for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign)))
    for assignment in assignments:
        targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
        value = assignment.value
        if not value or not any(
            isinstance(target, ast.Name) and target.id == "pytestmark" for target in targets
        ):
            continue
        for node in ast.walk(value):
            if not isinstance(node, ast.Attribute) or node.attr != "design_lint":
                continue
            mark = node.value
            if (
                isinstance(mark, ast.Attribute)
                and mark.attr == "mark"
                and isinstance(mark.value, ast.Name)
                and mark.value.id == "pytest"
            ):
                return True
    return False


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


def test_active_rule_fixture_modules_have_the_design_lint_marker() -> None:
    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    references = {
        reference
        for rule in catalog["rules"]
        if rule.get("status") == "active"
        for field in RULE_FIXTURE_FIELDS
        for reference in rule.get(field, [])
    }
    modules: dict[Path, set[str]] = {}
    unresolved: list[str] = []
    for reference in references:
        module = _fixture_module_path(reference)
        if module is None:
            unresolved.append(reference)
        else:
            modules.setdefault(module, set()).add(reference)

    unmarked = {
        path.relative_to(REPO_ROOT).as_posix(): sorted(references_for_module)
        for path, references_for_module in modules.items()
        if not _has_module_design_lint_marker(path)
    }

    assert not unresolved, f"Active rule fixtures must resolve to Python test modules: {unresolved}"
    assert not unmarked, (
        "Every active rule fault, control, and metamorphic fixture module must carry "
        f"pytest.mark.design_lint so focused runs select it: {unmarked}"
    )
