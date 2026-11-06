"""Capability dependency direction for rule and service owners."""

from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from kicad_tooling.hwrepo.surface_models import ToolSurfacesCatalog

pytestmark = pytest.mark.architecture

_REPOSITORY_ROOT = Path(__file__).parents[1]


@lru_cache(maxsize=1)
def _forbidden_surface_modules() -> frozenset[str]:
    catalog = read_model(_REPOSITORY_ROOT / "kicad_tooling/tool-surfaces.json", ToolSurfacesCatalog)
    # validate.py remains a registered CLI; its native work lives under hwrepo.
    return frozenset(
        item.module for item in catalog.cli if item.module != "kicad_tooling.validate"
    ) | {
        "kicad_tooling.cli",
        "kicad_tooling.mcp_server",
    }


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
            for forbidden in _forbidden_surface_modules()
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
        "from kicad_tooling.design_lint import main",
        "from kicad_tooling import release",
        "import kicad_tooling.check_all",
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
    prefixes = (
        "design_lint_",
        "electrical",
        "parts_",
        "cad_",
        "native_",
        "pcb_geometry_",
        "project_static_pipeline",
        "native_project_check",
        "schematic_geometry_",
    )
    standalone = {
        "design_lint",
        "layout",
        "selection",
        "schematic_geometry",
        "product",
        "artifact_access",
        "supplier_handoff",
        "bounded_file_content",
        "project_source_access",
        "purchasing_preferences",
        "release",
        "release_board_variant_selection",
        "portable_evidence",
        "pcb_return_path_capture",
        "pcb_drc_source_evidence",
        "pcb_drc_source_scan",
        "project_detail",
        "project_verification",
        "diagnostics",
        "releasing",
        "governance_lint",
        "governance_lint_catalog_policy",
        "governance_lint_filesystem_inputs",
        "governance_lint_inputs",
        "governance_lint_project_policy",
        "governance_lint_scope",
        "governance_records",
        "project_source_hashes",
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


def test_declared_source_hashing_has_one_owner_and_a_legacy_facade() -> None:
    owner = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/project_source_hashes.py"
    facade = _REPOSITORY_ROOT / "kicad_tooling/validate.py"
    owner_imports = _module_imports(
        owner.read_text(encoding="utf-8"), Path("kicad_tooling/hwrepo/project_source_hashes.py")
    )
    facade_tree = ast.parse(facade.read_text(encoding="utf-8"))
    legacy_export = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "hwrepo.project_source_hashes"
        and any(
            alias.name == "hash_project_sources" and alias.asname == "hashes"
            for alias in node.names
        )
        for node in ast.walk(facade_tree)
    )
    internal_uses_facade: list[str] = []
    for path in (_REPOSITORY_ROOT / "kicad_tooling").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.ImportFrom)
            and node.module == "validate"
            and node.level > 0
            and any(alias.name == "hashes" for alias in node.names)
            for node in ast.walk(tree)
        ):
            internal_uses_facade.append(str(path.relative_to(_REPOSITORY_ROOT)))

    assert "kicad_tooling.validate" not in owner_imports
    assert legacy_export
    assert not internal_uses_facade


def test_internal_modules_use_native_owners_instead_of_cli_facades() -> None:
    violations: list[str] = []
    package = _REPOSITORY_ROOT / "kicad_tooling"
    for path in package.rglob("*.py"):
        if path in {package / "validate.py", package / "check_toolchain.py"}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            (
                isinstance(node, ast.ImportFrom)
                and (
                    (node.level > 0 and node.module in {"validate", "check_toolchain"})
                    or (
                        node.level == 0
                        and node.module
                        in {
                            "kicad_tooling.validate",
                            "kicad_tooling.check_toolchain",
                        }
                    )
                )
            )
            or (
                isinstance(node, ast.Import)
                and any(
                    alias.name in {"kicad_tooling.validate", "kicad_tooling.check_toolchain"}
                    for alias in node.names
                )
            )
            for node in ast.walk(tree)
        ):
            violations.append(str(path.relative_to(_REPOSITORY_ROOT)))

    assert not violations, "Internal modules must import native capability owners: " + ", ".join(
        violations
    )


def test_project_source_operations_have_compatible_mcp_exports() -> None:
    from kicad_tooling.hwrepo import mcp_files, project_source_access

    for name in (
        "project_file_path",
        "read_project_file",
        "preview_project_edit",
        "apply_project_edit",
    ):
        assert getattr(mcp_files, name) is getattr(project_source_access, name)


def test_project_inventory_mcp_adapters_delegate_to_shared_services() -> None:
    server_path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/mcp_server.py"
    server_tree = ast.parse(server_path.read_text(encoding="utf-8"))
    server_calls = {
        node.func.id
        for node in ast.walk(server_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    adapter_path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/mcp_project_inventory.py"
    adapter_tree = ast.parse(adapter_path.read_text(encoding="utf-8"))
    handlers = {
        node.name: node
        for node in ast.walk(adapter_tree)
        if isinstance(node, ast.FunctionDef) and node.name in {"list_projects", "get_project"}
    }

    assert "register_project_inventory_tools" in server_calls
    assert set(handlers) == {"list_projects", "get_project"}
    project_calls = {
        node.func.id
        for node in ast.walk(handlers["get_project"])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "read_project_detail" in project_calls
    assert not {"inventory", "read_model", "repo_path"} & project_calls
    inventory_calls = {
        node.func.id
        for node in ast.walk(handlers["list_projects"])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "inventory" in inventory_calls


def test_findings_view_mcp_adapter_uses_the_shared_typed_export() -> None:
    server_path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/mcp_server.py"
    server_tree = ast.parse(server_path.read_text(encoding="utf-8"))
    server_calls = {
        node.func.id
        for node in ast.walk(server_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    adapter_path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/mcp_visualization_exports.py"
    adapter_tree = ast.parse(adapter_path.read_text(encoding="utf-8"))
    handler = next(
        node
        for node in ast.walk(adapter_tree)
        if isinstance(node, ast.FunctionDef) and node.name == "export_findings_view"
    )
    handler_calls = {
        node.func.id
        for node in ast.walk(handler)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "register_visualization_export_tools" in server_calls
    assert not any(
        isinstance(node, ast.FunctionDef) and node.name == "export_findings_view"
        for node in ast.walk(server_tree)
    )
    assert "build_findings_view" in handler_calls


def test_release_mcp_adapter_owns_registration_and_delegates_release_operations() -> None:
    server_path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/mcp_server.py"
    server_tree = ast.parse(server_path.read_text(encoding="utf-8"))
    server_calls = {
        node.func.id
        for node in ast.walk(server_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    adapter_path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/mcp_release.py"
    adapter_tree = ast.parse(adapter_path.read_text(encoding="utf-8"))
    handlers = {
        node.name: node
        for node in ast.walk(adapter_tree)
        if isinstance(node, ast.FunctionDef)
        and node.name in {"check_release", "verify_package", "package_release", "restore_package"}
    }
    delegated_operations = {
        node.func.attr
        for handler in handlers.values()
        for node in ast.walk(handler)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "register_release_tools" in server_calls
    assert set(handlers) == {
        "check_release",
        "verify_package",
        "package_release",
        "restore_package",
    }
    assert not any(
        isinstance(node, ast.FunctionDef)
        and node.name in {"check_release", "verify_package", "package_release", "restore_package"}
        for node in ast.walk(server_tree)
    )
    assert {"check_release", "verify_package", "package_release", "restore_package"} <= (
        delegated_operations
    )
