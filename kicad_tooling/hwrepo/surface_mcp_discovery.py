"""Static discovery of MCP tool declarations without importing the optional SDK."""

from __future__ import annotations

import ast
from pathlib import Path

from .contracts import repo_path
from .surface_ast import is_tool_call, string
from .surface_models import ToolMcpSnapshot


def _import_base(package: tuple[str, ...], level: int, module: str | None) -> tuple[str, ...]:
    if level:
        base = package[: len(package) - level + 1]
    else:
        base = ()
    return (*base, *(module.split(".") if module else ()))


def _module_path(root: Path, parts: tuple[str, ...]) -> Path:
    if not parts or parts[0] != "kicad_tooling":
        raise ValueError(f"MCP registrar must be in kicad_tooling: {'.'.join(parts)}")
    stem = "/".join(parts)
    module_file = repo_path(root, f"{stem}.py")
    if module_file.is_file():
        return module_file
    package_file = repo_path(root, f"{stem}/__init__.py")
    if package_file.is_file():
        return package_file
    raise ValueError(f"MCP registrar source does not exist: {'.'.join(parts)}")


def _called_registrars(root: Path, path: Path, tree: ast.Module) -> tuple[tuple[Path, str], ...]:
    package = path.relative_to(root).with_suffix("").parts[:-1]
    imported_functions: dict[str, tuple[tuple[str, ...], str]] = {}
    imported_modules: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            base = _import_base(package, node.level, node.module)
            for alias in node.names:
                local_name = alias.asname or alias.name
                if node.module is None:
                    imported_modules[local_name] = (*base, alias.name)
                elif alias.name.startswith("register_"):
                    imported_functions[local_name] = (base, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                module_parts = tuple(alias.name.split("."))
                local_name = alias.asname or module_parts[0]
                imported_modules[local_name] = module_parts if alias.asname else module_parts[:1]

    called: set[tuple[tuple[str, ...], str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in imported_functions:
            called.add(imported_functions[node.func.id])
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("register_")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in imported_modules
        ):
            called.add((imported_modules[node.func.value.id], node.func.attr))

    owners: list[tuple[Path, str]] = []
    for module_parts, function_name in sorted(called):
        owner_path = _module_path(root, module_parts)
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"), filename=str(owner_path))
        if not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
            for node in owner_tree.body
        ):
            raise ValueError(
                f"MCP registrar {function_name} is not declared in {owner_path.relative_to(root)}"
            )
        owners.append((owner_path, function_name))
    return tuple(owners)


def _discover_registrations(path: Path, scope: ast.AST) -> tuple[ToolMcpSnapshot, ...]:
    functions = {
        node.name: node
        for node in ast.walk(scope)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    snapshots: list[ToolMcpSnapshot] = []
    recognized: set[int] = set()
    for node in ast.walk(scope):
        function: ast.FunctionDef | ast.AsyncFunctionDef | None = None
        declaration: ast.Call | None = None
        if isinstance(node, ast.Call) and is_tool_call(node.func):
            registration_args: list[ast.expr] = node.args
            if len(registration_args) != 1 or not isinstance(registration_args[0], ast.Name):
                raise ValueError(f"{path}:{node.lineno}: unsupported MCP tool registration")
            function = functions.get(registration_args[0].id)
            declaration = node.func if isinstance(node.func, ast.Call) else None
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = [value for value in node.decorator_list if is_tool_call(value)]
            if decorators:
                if len(decorators) != 1:
                    raise ValueError(f"{path}:{node.lineno}: repeated MCP tool decorator")
                function = node
                declaration = decorators[0] if isinstance(decorators[0], ast.Call) else None
        if declaration is None:
            continue
        if function is None or declaration.args:
            raise ValueError(f"{path}:{declaration.lineno}: unsupported MCP tool registration")
        recognized.add(id(declaration))
        name = function.name
        for keyword in declaration.keywords:
            if keyword.arg == "name":
                name = string(keyword.value, f"{path}:{declaration.lineno}")
        arguments = function.args
        if arguments.vararg is not None or arguments.kwarg is not None:
            raise ValueError(
                f"{path}:{declaration.lineno}: variadic MCP tool parameters are unsupported"
            )
        parameters = tuple(
            sorted(
                argument.arg
                for argument in (
                    *arguments.posonlyargs,
                    *arguments.args,
                    *arguments.kwonlyargs,
                )
            )
        )
        snapshots.append(ToolMcpSnapshot(name=name, parameters=parameters))
    if any(is_tool_call(node) and id(node) not in recognized for node in ast.walk(scope)):
        raise ValueError(f"{path}: unsupported dynamic MCP tool registration")
    return tuple(snapshots)


def discover_mcp(root: Path) -> tuple[ToolMcpSnapshot, ...]:
    """Read direct and imported registration owners as source, without importing them."""
    path = repo_path(root, "kicad_tooling/hwrepo/mcp_server.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    snapshots = list(_discover_registrations(path, tree))
    for owner_path, function_name in _called_registrars(root, path, tree):
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"), filename=str(owner_path))
        registrar = next(
            node
            for node in owner_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        )
        snapshots.extend(_discover_registrations(owner_path, registrar))
    return tuple(sorted(snapshots, key=lambda item: item.name))
