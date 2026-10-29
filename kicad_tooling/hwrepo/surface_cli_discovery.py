"""Static discovery of first-party Python CLI modules and declarations."""

from __future__ import annotations

import ast
from pathlib import Path

from .contracts import repo_path
from .surface_ast import is_main_guard, string, strings
from .surface_models import ToolCliSnapshot


def discover_cli(root: Path) -> tuple[ToolCliSnapshot, ...]:
    """Discover first-party Python CLI modules, command choices and option names."""
    snapshots: list[ToolCliSnapshot] = []
    for candidate in sorted(repo_path(root, "kicad_tooling").rglob("*.py")):
        path = repo_path(root, candidate.relative_to(root).as_posix())
        if not path.is_file():
            raise ValueError(f"CLI source must be a regular file: {path}")
        if path.name == "__main__.py":
            # The installed entry point dispatches existing commands; it adds no
            # new workflow capability of its own.
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        is_cli = any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main"
            for node in tree.body
        ) or any(is_main_guard(node) for node in ast.walk(tree))
        if not is_cli:
            continue
        commands: set[str] = set()
        options: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            location = f"{path.relative_to(root)}:{node.lineno}"
            if node.func.attr == "add_parser":
                if not node.args:
                    raise ValueError(f"{location}: subcommand name is missing")
                commands.add(string(node.args[0], location))
                for keyword in node.keywords:
                    if keyword.arg == "aliases":
                        commands.update(strings(keyword.value, location))
            if node.func.attr != "add_argument":
                continue
            names = tuple(string(value, location) for value in node.args)
            options.update(name for name in names if name.startswith("-"))
            if names and not names[0].startswith("-"):
                for keyword in node.keywords:
                    if keyword.arg == "choices":
                        commands.update(strings(keyword.value, location))
        module = ".".join(path.relative_to(root).with_suffix("").parts)
        snapshots.append(
            ToolCliSnapshot(
                module=module,
                commands=tuple(sorted(commands)),
                options=tuple(sorted(options)),
            )
        )
    return tuple(snapshots)
