"""Capability dependency direction for rule and service owners."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

pytestmark = pytest.mark.architecture

_REPOSITORY_ROOT = Path(__file__).parents[1]
_FORBIDDEN_SURFACE_MODULES = frozenset(
    {
        "kicad_tooling.cli",
        "kicad_tooling.mcp_server",
        "kicad_tooling.template",
        "kicad_tooling.ci",
        "kicad_tooling.ci_hosted",
    }
)


def _module_imports(source: str, owner_path: Path) -> tuple[str, ...]:
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module is not None:
                imports.add(node.module)
                imports.update(f"{node.module}.{alias.name}" for alias in node.names)
                continue
            package = list(owner_path.with_suffix("").parts[:-1])
            base = package[: len(package) - node.level + 1]
            if node.module:
                base.extend(node.module.split("."))
                imports.add(".".join(base))
                imports.update(".".join((*base, alias.name)) for alias in node.names)
            else:
                imports.update(".".join((*base, alias.name)) for alias in node.names)
    return tuple(sorted(imports))


def _surface_dependencies(imports: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        item
        for item in imports
        if any(
            item == forbidden or item.startswith(f"{forbidden}.")
            for forbidden in _FORBIDDEN_SURFACE_MODULES
        )
        or item.startswith("kicad_tooling.hwrepo.mcp_")
    )


def test_active_rule_predicates_do_not_depend_on_application_surfaces() -> None:
    owners = sorted({rule.implementation_owner for rule in rule_catalog().rules})
    violations: list[str] = []
    for owner in owners:
        owner_file, _separator, _function = owner.partition("#")
        relative_path = Path(owner_file)
        if "/" not in owner_file:
            relative_path = Path(*owner_file.split(".")).with_suffix(".py")
        path = _REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        dependencies = _surface_dependencies(_module_imports(source, relative_path))
        violations.extend(f"{owner} imports {dependency}" for dependency in dependencies)

    assert not violations, "Rule predicates must not depend on CLI/MCP/CI surfaces:\n" + "\n".join(
        violations
    )


@pytest.mark.parametrize(
    "source",
    (
        "from kicad_tooling.mcp_server import create_server",
        "import kicad_tooling.cli",
        "from kicad_tooling.ci import static_pipeline",
        "from kicad_tooling import ci",
        "from .. import ci",
        "from .mcp_files import read_project_file",
        "from . import mcp_files",
        "import kicad_tooling.hwrepo.mcp_workflow",
    ),
)
def test_surface_dependency_guard_rejects_transport_and_ci_imports(source: str) -> None:
    assert _surface_dependencies(_module_imports(source, Path("kicad_tooling/hwrepo/sample.py")))


def test_domain_imports_are_not_rejected_as_surface_dependencies() -> None:
    imports = _module_imports(
        "from kicad_tooling.hwrepo import design_lint_types\n"
        "from kicad_tooling.validate import read_netlist",
        Path("sample.py"),
    )

    assert _surface_dependencies(imports) == ()


def test_stable_capability_services_do_not_depend_on_application_surfaces() -> None:
    directory = _REPOSITORY_ROOT / "kicad_tooling/hwrepo"
    prefixes = ("electrical", "parts_", "cad_")
    standalone = {
        "layout",
        "selection",
        "product",
        "artifact_access",
        "supplier_handoff",
        "bounded_file_content",
        "project_source_access",
        "purchasing_preferences",
    }
    paths = sorted(
        path
        for path in directory.glob("*.py")
        if path.stem.startswith(prefixes) or path.stem in standalone
    )
    names = {path.stem for path in paths}
    assert standalone <= names
    assert all(any(name.startswith(prefix) for name in names) for prefix in prefixes)
    violations: list[str] = []
    for path in paths:
        relative = path.relative_to(_REPOSITORY_ROOT)
        dependencies = _surface_dependencies(
            _module_imports(path.read_text(encoding="utf-8"), relative)
        )
        violations.extend(f"{relative} imports {dependency}" for dependency in dependencies)
    assert not violations, "Capability services must not import surfaces:\n" + "\n".join(violations)


def test_project_source_operations_have_compatible_mcp_exports() -> None:
    from kicad_tooling.hwrepo import mcp_files, project_source_access

    for name in (
        "project_file_path",
        "read_project_file",
        "preview_project_edit",
        "apply_project_edit",
    ):
        assert getattr(mcp_files, name) is getattr(project_source_access, name)
