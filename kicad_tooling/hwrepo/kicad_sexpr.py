"""Typed source spans and token helpers for KiCad S-expression files."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class SExprSpan:
    """Half-open character offsets for one source expression."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class SExprToken:
    """Half-open source offsets and quoting state for one atom."""

    start: int
    end: int
    quoted: bool


SExprProperties: TypeAlias = Mapping[str, SExprSpan]


def sexpr_children(text: str, start: int, end: int) -> tuple[SExprSpan, ...]:
    """Return direct S-expression children, respecting strings and comments."""
    children: list[SExprSpan] = []
    depth = 0
    opening = 0
    quoted = False
    escaped = False
    comment = False
    for position in range(start, end):
        char = text[position]
        if comment:
            if char == "\n":
                comment = False
            continue
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == "#":
            comment = True
        elif char == '"':
            quoted = True
        elif char == "(":
            if depth == 0:
                opening = position
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise ValueError("Unmatched closing parenthesis in PCB source")
            if depth == 0:
                children.append(SExprSpan(opening, position + 1))
    if quoted:
        raise ValueError("Unterminated quoted string in PCB source")
    if depth:
        raise ValueError("Unclosed parenthesis in PCB source")
    return tuple(children)


def sexpr_atoms(text: str, span: SExprSpan) -> tuple[str, ...]:
    """Read a node's leading atoms, before its first child expression."""
    values: list[str] = []
    position = span.start + 1
    while position < span.end - 1:
        while position < span.end - 1 and text[position].isspace():
            position += 1
        if position >= span.end - 1 or text[position] in "()":
            break
        if text[position] == "#":
            newline = text.find("\n", position, span.end)
            if newline < 0:
                break
            position = newline + 1
            continue
        if text[position] == '"':
            position += 1
            value: list[str] = []
            while position < span.end - 1:
                char = text[position]
                if char == "\\" and position + 1 < span.end - 1:
                    following = text[position + 1]
                    # Only quote and backslash need unescaping for model paths.
                    value.append(following if following in {'"', "\\"} else "\\" + following)
                    position += 2
                elif char == '"':
                    position += 1
                    break
                else:
                    value.append(char)
                    position += 1
            else:
                raise ValueError("Unterminated quoted atom in PCB source")
            values.append("".join(value))
        else:
            start = position
            while (
                position < span.end - 1
                and not text[position].isspace()
                and text[position] not in "()"
            ):
                position += 1
            values.append(text[start:position])
    return tuple(values)


def sexpr_tokens(source: str, span: SExprSpan) -> tuple[SExprToken, ...]:
    """Return source offsets for the leading tokens of one expression."""
    tokens: list[SExprToken] = []
    position = span.start + 1
    while position < span.end - 1:
        if source[position].isspace():
            position += 1
            continue
        if source[position] in "()":
            break
        if source[position] == "#":
            newline = source.find("\n", position, span.end)
            position = span.end if newline == -1 else newline + 1
            continue
        start = position
        quoted = source[position] == '"'
        if quoted:
            position += 1
            while position < span.end - 1:
                if source[position] == "\\":
                    position += 2
                elif source[position] == '"':
                    position += 1
                    break
                else:
                    position += 1
            else:
                raise ValueError("Unterminated CAD property string")
        else:
            while (
                position < span.end - 1
                and not source[position].isspace()
                and source[position] not in "()"
            ):
                position += 1
        tokens.append(SExprToken(start, position, quoted))
    return tuple(tokens)


def sexpr_root(source: str, kind: str) -> SExprSpan:
    """Require one named root expression and no non-comment text outside it."""
    roots = sexpr_children(source, 0, len(source))
    if len(roots) != 1 or sexpr_atoms(source, roots[0])[:1] != (kind,):
        raise ValueError(f"Expected exactly one {kind} root")
    for outside in (source[: roots[0].start], source[roots[0].end :]):
        if any(line.split("#", 1)[0].strip() for line in outside.splitlines()):
            raise ValueError(f"Unexpected text outside {kind} root")
    return roots[0]


def sexpr_nodes(source: str, parent: SExprSpan, name: str) -> tuple[SExprSpan, ...]:
    """Select direct children whose first atom has the requested name."""
    return tuple(
        child
        for child in sexpr_children(source, parent.start + 1, parent.end - 1)
        if sexpr_atoms(source, child)[:1] == (name,)
    )


def sexpr_field(
    source: str, parent: SExprSpan, name: str, *, required: bool = True
) -> tuple[str, ...]:
    """Read one named field's values, rejecting duplicate or missing required fields."""
    found = sexpr_nodes(source, parent, name)
    if len(found) > 1 or (required and not found):
        raise ValueError(f"Expected one {name} node in CAD source")
    if not found:
        return ()
    return sexpr_atoms(source, found[0])[1:]


def sexpr_scalar(source: str, parent: SExprSpan, name: str, *, default: str | None = None) -> str:
    """Read one scalar field, using a default only when the field is absent."""
    values = sexpr_field(source, parent, name, required=default is None)
    if not values and default is not None:
        return default
    if len(values) != 1:
        raise ValueError(f"Expected a single {name} value in CAD source")
    return values[0]


def sexpr_properties(source: str, parent: SExprSpan) -> SExprProperties:
    """Index quoted CAD property names and value spans, rejecting duplicates."""
    result: dict[str, SExprSpan] = {}
    for node in sexpr_nodes(source, parent, "property"):
        atoms = sexpr_atoms(source, node)
        if len(atoms) != 3 or not atoms[1] or atoms[1] in result:
            raise ValueError("Malformed or duplicate CAD property")
        tokens = sexpr_tokens(source, node)
        if len(tokens) != 3 or not tokens[1].quoted or not tokens[2].quoted:
            raise ValueError("CAD property names and values must be quoted strings")
        result[atoms[1]] = node
    return MappingProxyType(result)


def sexpr_property_value(
    source: str, properties: SExprProperties, name: str, *, required: bool = False
) -> str:
    """Return one indexed property's decoded value, or an empty optional value."""
    if name not in properties:
        if required:
            raise ValueError(f"Missing {name} property")
        return ""
    return sexpr_atoms(source, properties[name])[2]


def quote_sexpr_atom(value: str) -> str:
    """Quote one replacement atom after rejecting control characters."""
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Reviewed CAD field contains a control character")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
