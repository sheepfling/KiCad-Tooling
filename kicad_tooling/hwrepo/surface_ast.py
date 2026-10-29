"""Literal and declaration helpers shared by static surface discovery."""

from __future__ import annotations

import ast
from types import EllipsisType


def literal_string(expression: ast.expr) -> str | None:
    if not isinstance(expression, ast.Constant):
        return None
    value: str | bytes | int | float | complex | bool | None | EllipsisType = expression.value
    return value if isinstance(value, str) else None


def strings(node: ast.AST, location: str) -> tuple[str, ...]:
    if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        raise ValueError(  # noqa: TRY004 - preserve the parser's established value-error contract
            f"{location}: surface choices must be literal strings"
        )
    elements: list[ast.expr] = node.elts
    values = tuple(literal_string(item) for item in elements)
    if any(value is None for value in values):
        raise ValueError(f"{location}: surface choices must be literal strings")
    return tuple(value for value in values if value is not None)


def string(node: ast.expr, location: str) -> str:
    value = literal_string(node)
    if value is None:
        raise TypeError(f"{location}: surface name must be a literal string")
    return value


def is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.Compare):
        return False
    left: ast.expr = node.left
    if not isinstance(left, ast.Name) or left.id != "__name__":
        return False
    comparators: list[ast.expr] = node.comparators
    return any(literal_string(value) == "__main__" for value in comparators)


def is_tool_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "tool"
    )
